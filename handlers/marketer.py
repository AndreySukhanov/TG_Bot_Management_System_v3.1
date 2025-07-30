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
from db.database import PaymentDB, BalanceDB, ProjectDB
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
                "❌ <b>Не удалось распознать заявку на оплату.</b>\n\n"
                "Теперь поддерживается естественный язык! Примеры:\n"
                "• <code>Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту</code>\n"
                "• <code>Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890</code>\n"
                "• <code>Оплати инстаграм 200$ проект Гамма счет 1234-5678</code>\n\n"
                "Отправьте /help для просмотра всех примеров.",
                parse_mode="HTML"
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
        
        # Валидация проекта
        project_exists = await ProjectDB.project_exists(payment_data["project_name"])
        if not project_exists:
            # Получаем список активных проектов для подсказки
            active_projects = await ProjectDB.get_project_names()
            
            error_message = f"❌ <b>Проект '{payment_data['project_name']}' не найден или неактивен.</b>\n\n"
            
            if active_projects:
                error_message += "📋 <b>Доступные проекты:</b>\n"
                for project in active_projects:
                    error_message += f"• {project}\n"
                error_message += "\n💡 Используйте точное название проекта из списка выше."
            else:
                error_message += "📋 <b>Нет активных проектов.</b>\n\n"
                error_message += "ℹ️ Обратитесь к руководителю для создания проекта."
            
            await message.answer(error_message, parse_mode="HTML")
            return
        
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
            f"✅ <b>Заявка создана успешно!</b>\n\n"
            f"📋 <b>ID заявки:</b> <code>{payment_id}</code>\n"
            f"🛍️ <b>Сервис:</b> {payment_data['service_name']}\n"
            f"💰 <b>Сумма:</b> {payment_data['amount']}$\n"
            f"🏷️ <b>Проект:</b> {payment_data['project_name']}\n"
            f"💳 <b>Способ оплаты:</b> {payment_data['payment_method']}\n"
            f"📝 <b>Детали:</b> {payment_data['payment_details']}\n\n"
            f"⏳ Статус: Ожидает оплаты\n"
            f"Финансист получил уведомление.",
            parse_mode="HTML"
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
        f"🔔 <b>НОВАЯ ЗАЯВКА НА ОПЛАТУ</b>\n\n"
        f"📋 <b>ID:</b> <code>{payment_id}</code>\n"
        f"🛍️ <b>Сервис:</b> {payment_data['service_name']}\n"
        f"💰 <b>Сумма:</b> {payment_data['amount']}$\n"
        f"🏷️ <b>Проект:</b> {payment_data['project_name']}\n"
        f"💳 <b>Способ оплаты:</b> {payment_data['payment_method']}\n"
        f"📝 <b>Детали:</b> {payment_data['payment_details']}\n\n"
        f"💸 Для подтверждения оплаты отправьте:\n"
        f"<code>Оплачено {payment_id}</code> + прикрепите подтверждение"
    )
    
    for financier_id in config.FINANCIERS:
        try:
            await bot.send_message(
                financier_id, 
                notification_text, 
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление финансисту {financier_id}: {e}")


async def notify_managers_low_balance(bot):
    """Уведомление руководителей о низком балансе"""
    config = Config()
    current_balance = await BalanceDB.get_balance()
    
    notification_text = (
        f"⚠️ <b>НИЗКИЙ БАЛАНС!</b>\n\n"
        f"💰 <b>Текущий баланс:</b> {current_balance:.2f}$\n"
        f"📉 <b>Порог:</b> {config.LOW_BALANCE_THRESHOLD}$\n\n"
        f"💳 Необходимо пополнение баланса!"
    )
    
    for manager_id in config.MANAGERS:
        try:
            await bot.send_message(
                manager_id,
                notification_text,
                parse_mode="HTML"
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


async def my_payments_handler(message: Message):
    """Показать заявки маркетолога"""
    try:
        from db.database import PaymentDB
        
        marketer_id = message.from_user.id
        payments = await PaymentDB.get_payments_by_marketer(marketer_id)
        
        if not payments:
            await message.answer(
                "📝 <b>Ваши заявки</b>\n\n"
                "У вас пока нет заявок на оплату.\n\n"
                "Создайте заявку голосовым сообщением или текстом:\n"
                "• 'Нужна оплата Фейсбук 100$ проект Альфа'\n"
                "• 'Оплати Гугл Адс 50 долларов криптой'",
                parse_mode="HTML"
            )
            return
            
        # Группируем по статусам
        pending = [p for p in payments if p['status'] == 'pending']
        paid = [p for p in payments if p['status'] == 'paid']
        
        message_parts = ["📝 <b>Ваши заявки</b>\n"]
        
        if pending:
            message_parts.append("⏳ <b>Ожидают подтверждения:</b>")
            for payment in pending[-5:]:  # Последние 5
                message_parts.append(
                    f"• ID {payment['id']}: <b>{payment['amount']}$</b> - {payment['service_name']}\n"
                    f"  📋 {payment['project_name']} | 💳 {payment['payment_method']}"
                )
            message_parts.append("")
            
        if paid:
            message_parts.append("✅ <b>Последние оплаченные:</b>")
            for payment in paid[-3:]:  # Последние 3
                message_parts.append(
                    f"• ID {payment['id']}: <b>{payment['amount']}$</b> - {payment['service_name']}"
                )
            message_parts.append("")
            
        message_parts.append(f"📊 <b>Всего заявок:</b> {len(payments)}")
        
        await message.answer(
            "\n".join(message_parts),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения заявок маркетолога: {e}")
        await message.answer("❌ Ошибка при получении заявок. Попробуйте позже.")


async def last_payment_handler(message: Message):
    """Показать последнюю заявку маркетолога"""
    try:
        from db.database import PaymentDB
        
        marketer_id = message.from_user.id
        payments = await PaymentDB.get_payments_by_marketer(marketer_id)
        
        if not payments:
            await message.answer(
                "📝 <b>Последняя заявка</b>\n\n"
                "У вас пока нет заявок на оплату.\n\n"
                "Создайте заявку голосовым сообщением или текстом:\n"
                "• 'Нужна оплата Фейсбук 100$ проект Альфа'\n"
                "• 'Оплати Гугл Адс 50 долларов криптой'",
                parse_mode="HTML"
            )
            return
            
        # Берем самую последнюю заявку
        last_payment = payments[0]
        
        # Статус с эмодзи
        status_emoji = {
            'pending': '⏳ Ожидает подтверждения',
            'paid': '✅ Оплачена',
            'rejected': '❌ Отклонена'
        }.get(last_payment['status'], f"❓ {last_payment['status']}")
        
        # Форматируем дату создания
        created_date = last_payment['created_at'][:16].replace('T', ' ')
        
        await message.answer(
            f"📝 <b>Последняя заявка</b>\n\n"
            f"🆔 <b>ID:</b> {last_payment['id']}\n"
            f"💰 <b>Сумма:</b> {last_payment['amount']}$\n"
            f"🛍️ <b>Сервис:</b> {last_payment['service_name']}\n"
            f"📋 <b>Проект:</b> {last_payment['project_name']}\n"
            f"💳 <b>Способ оплаты:</b> {last_payment['payment_method']}\n"
            f"📅 <b>Создана:</b> {created_date}\n"
            f"📊 <b>Статус:</b> {status_emoji}\n\n"
            f"💡 Для просмотра всех заявок скажите: 'Мои заявки'",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения последней заявки: {e}")
        await message.answer("❌ Ошибка при получении заявки. Попробуйте позже.") 