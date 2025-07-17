"""
Обработчики для маркетологов.
Обрабатывает заявки на оплату и уведомления о статусе.
"""

from aiogram import Dispatcher, F
from aiogram.types import Message, Document, PhotoSize
from utils.config import Config
from utils.logger import log_action
from nlp.parser import PaymentParser
from nlp.hybrid_parser import HybridPaymentParser
from handlers.nlp_command_handler import smart_message_router
from db.database import PaymentDB, BalanceDB
from utils.file_handler import save_file
import logging
import re

logger = logging.getLogger(__name__)


async def payment_request_handler(message: Message):
    """Обработчик заявок на оплату от маркетологов"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "marketer":
        return
    
    # Сначала проверяем, не является ли это командой
    if await smart_message_router(message):
        return  # Сообщение обработано как команда
    
    log_action(user_id, "payment_request", message.text or message.caption or "")
    
    try:
        # Парсинг сообщения с использованием гибридного подхода
        parser = HybridPaymentParser()
        message_text = message.text or message.caption or ""
        payment_data = await parser.parse_payment_message(message_text)
        
        if not payment_data:
            await message.answer(
                "❌ **Не удалось распознать заявку на оплату.**\n\n"
                "Теперь поддерживается естественный язык! Примеры:\n"
                "• `Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту`\n"
                "• `Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890`\n"
                "• `Оплати инстаграм 200$ проект Гамма счет 1234-5678`\n\n"
                "Отправьте /help для просмотра всех примеров.",
                parse_mode="Markdown"
            )
            return
        
        # Обработка прикрепленного файла
        file_path = None
        if message.document or message.photo:
            try:
                file_path = await save_file(message)
                if payment_data["payment_method"] == "file":
                    payment_data["payment_details"] = f"Файл: {file_path}"
            except ValueError as e:
                logger.error(f"Ошибка размера файла: {e}")
                await message.answer(f"⚠️ {str(e)}")
                return
            except Exception as e:
                logger.error(f"Ошибка сохранения файла: {e}")
                await message.answer("⚠️ Не удалось сохранить прикрепленный файл, но заявка будет создана.")
        
        # Создание заявки в базе данных
        payment_id = await PaymentDB.create_payment(
            marketer_id=user_id,
            service_name=payment_data["service_name"],
            amount=payment_data["amount"],
            payment_method=payment_data["payment_method"],
            payment_details=payment_data["payment_details"],
            project_name=payment_data["project_name"],
            file_path=file_path
        )
        
        # Отправка подтверждения маркетологу
        await message.answer(
            f"✅ **Заявка создана успешно!**\n\n"
            f"📋 **ID заявки:** `{payment_id}`\n"
            f"🛍️ **Сервис:** {payment_data['service_name']}\n"
            f"💰 **Сумма:** {payment_data['amount']}$\n"
            f"🏷️ **Проект:** {payment_data['project_name']}\n"
            f"💳 **Способ оплаты:** {payment_data['payment_method']}\n"
            f"📝 **Детали:** {payment_data['payment_details']}\n\n"
            f"⏳ Статус: Ожидает оплаты\n"
            f"Финансист получил уведомление.",
            parse_mode="Markdown"
        )
        
        # Отправка уведомления финансистам
        await notify_financiers_about_payment(message.bot, payment_id, payment_data)
        
    except ValueError as e:
        logger.error(f"Ошибка валидации данных платежа: {e}")
        await message.answer(
            f"❌ Ошибка в данных заявки: {str(e)}\n"
            "Проверьте правильность заполнения всех полей."
        )
    except Exception as e:
        logger.error(f"Ошибка обработки заявки на оплату: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке заявки.\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


async def notify_financiers_about_payment(bot, payment_id: int, payment_data: dict):
    """Уведомление финансистов о новой заявке"""
    config = Config()
    
    notification_text = (
        f"🔔 **НОВАЯ ЗАЯВКА НА ОПЛАТУ**\n\n"
        f"📋 **ID:** `{payment_id}`\n"
        f"🛍️ **Сервис:** {payment_data['service_name']}\n"
        f"💰 **Сумма:** {payment_data['amount']}$\n"
        f"🏷️ **Проект:** {payment_data['project_name']}\n"
        f"💳 **Способ оплаты:** {payment_data['payment_method']}\n"
        f"📝 **Детали:** {payment_data['payment_details']}\n\n"
        f"💸 Для подтверждения оплаты отправьте:\n"
        f"`Оплачено {payment_id}` + прикрепите подтверждение"
    )
    
    for financier_id in config.FINANCIERS:
        try:
            await bot.send_message(
                financier_id, 
                notification_text, 
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление финансисту {financier_id}: {e}")


async def notify_managers_low_balance(bot):
    """Уведомление руководителей о низком балансе"""
    config = Config()
    current_balance = await BalanceDB.get_balance()
    
    notification_text = (
        f"⚠️ **НИЗКИЙ БАЛАНС!**\n\n"
        f"💰 **Текущий баланс:** {current_balance:.2f}$\n"
        f"📉 **Порог:** {config.LOW_BALANCE_THRESHOLD}$\n\n"
        f"💳 Необходимо пополнение баланса!"
    )
    
    for manager_id in config.MANAGERS:
        try:
            await bot.send_message(
                manager_id,
                notification_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление руководителю {manager_id}: {e}")


def setup_marketer_handlers(dp: Dispatcher):
    """Регистрация обработчиков для маркетологов"""
    
    def is_marketer(message: Message) -> bool:
        return Config.get_user_role(message.from_user.id) == "marketer"
    
    # Обработчик заявок на оплату (любой текст от маркетолога)
    dp.message.register(
        payment_request_handler,
        F.text & (~F.text.regexp(r"^/", flags=re.IGNORECASE)),  # не команды
        is_marketer
    )
    # Обработчик для сообщений с документами/фото от маркетологов (любая подпись)
    dp.message.register(
        payment_request_handler,
        (F.document | F.photo) & (~F.caption.regexp(r"^/", flags=re.IGNORECASE)),
        is_marketer
    ) 