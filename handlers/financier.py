"""
Обработчики для финансистов.
Обрабатывает подтверждения оплаты и команды баланса.
"""

import re
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from utils.config import Config
from utils.logger import log_action
from db.database import PaymentDB, BalanceDB
from utils.file_handler import save_file
from handlers.nlp_command_handler import smart_message_router
import logging

logger = logging.getLogger(__name__)


async def payment_confirmation_handler(message: Message):
    """Обработчик подтверждения оплаты"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "financier":
        return
    
    # Сначала проверяем, не является ли это командой
    if await smart_message_router(message):
        return  # Сообщение обработано как команда
    
    log_action(user_id, "payment_confirmation", message.text)
    
    try:
        # Извлечение ID платежа из сообщения
        text = message.text or message.caption or ""
        match = re.search(r"оплачено\s+(\d+)", text, re.IGNORECASE)
        
        if not match:
            await message.answer(
                "❌ <b>Неверный формат подтверждения.</b>\n\n"
                "Используйте формат:\n"
                "<code>Оплачено [ID_ЗАЯВКИ]</code> + прикрепите подтверждение\n\n"
                "Пример: <code>Оплачено 123</code>",
                parse_mode="HTML"
            )
            return
        
        payment_id = int(match.group(1))
        
        # Проверка существования платежа
        payment = await PaymentDB.get_payment(payment_id)
        if not payment:
            await message.answer(
                f"❌ Заявка с ID <code>{payment_id}</code> не найдена.",
                parse_mode="HTML"
            )
            return
        
        if payment["status"] != "pending":
            await message.answer(
                f"❌ Заявка <code>{payment_id}</code> уже обработана.\n"
                f"Текущий статус: <b>{payment['status']}</b>",
                parse_mode="HTML"
            )
            return
        
        # Обработка подтверждения
        confirmation_hash = None
        confirmation_file = None
        
        # Извлечение хэша из текста
        hash_match = re.search(r"хэш[:=]\s*([0-9a-fA-F]+)", text, re.IGNORECASE)
        if hash_match:
            confirmation_hash = hash_match.group(1)
        
        # Сохранение прикрепленного файла
        if message.document or message.photo:
            try:
                confirmation_file = await save_file(message)
            except ValueError as e:
                logger.error(f"Ошибка размера файла подтверждения: {e}")
                await message.answer(f"⚠️ {str(e)}")
                return
            except Exception as e:
                logger.error(f"Ошибка сохранения файла подтверждения: {e}")
                await message.answer("⚠️ Не удалось сохранить прикрепленный файл.")
        
        # Обновление статуса платежа
        await PaymentDB.update_payment_status(
            payment_id=payment_id,
            status="paid",
            confirmation_hash=confirmation_hash,
            confirmation_file=confirmation_file
        )
        
        # Списание с баланса при подтверждении оплаты
        await BalanceDB.subtract_balance(
            payment["amount"], 
            payment_id, 
            f"Оплата {payment['service_name']} для {payment['project_name']}"
        )
        
        # Отправка подтверждения финансисту
        await message.answer(
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"📋 <b>ID заявки:</b> <code>{payment_id}</code>\n"
            f"🛍️ <b>Сервис:</b> {payment['service_name']}\n"
            f"💰 <b>Сумма:</b> {payment['amount']}$\n"
            f"🏷️ <b>Проект:</b> {payment['project_name']}\n\n"
            f"✅ Маркетолог получил уведомление об оплате.",
            parse_mode="HTML"
        )
        
        # Уведомление маркетолога
        await notify_marketer_payment_confirmed(
            message.bot, 
            payment["marketer_id"], 
            payment_id, 
            payment
        )
        
        # Проверка низкого баланса после списания
        if await BalanceDB.should_send_low_balance_alert():
            await notify_managers_low_balance(message.bot)
            await BalanceDB.update_low_balance_alert()
        
    except ValueError:
        await message.answer(
            "❌ Неверный ID заявки. Используйте числовой ID.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка подтверждения оплаты: {e}")
        await message.answer(
            "❌ Произошла ошибка при подтверждении оплаты.\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


async def balance_command_handler(message: Message):
    """Обработчик команды /balance для финансистов"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) not in ["financier", "manager"]:
        await message.answer("❌ У вас нет доступа к информации о балансе.")
        return
    
    log_action(user_id, "balance_check", "")
    
    try:
        current_balance = await BalanceDB.get_balance()
        
        status_emoji = "✅" if current_balance >= config.LOW_BALANCE_THRESHOLD else "⚠️"
        
        await message.answer(
            f"{status_emoji} <b>ТЕКУЩИЙ БАЛАНС</b>\n\n"
            f"💰 <b>Сумма:</b> {current_balance:.2f}$\n"
            f"📊 <b>Порог:</b> {config.LOW_BALANCE_THRESHOLD}$\n\n"
            f"{'🟢 Баланс в норме' if current_balance >= config.LOW_BALANCE_THRESHOLD else '🔴 Требуется пополнение'}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        await message.answer(
            "❌ Произошла ошибка при получении информации о балансе."
        )


async def notify_marketer_payment_confirmed(bot, marketer_id: int, payment_id: int, payment: dict):
    """Уведомление маркетолога о подтверждении оплаты"""
    
    notification_text = (
        f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
        f"📋 <b>ID заявки:</b> <code>{payment_id}</code>\n"
        f"🛍️ <b>Сервис:</b> {payment['service_name']}\n"
        f"💰 <b>Сумма:</b> {payment['amount']}$\n"
        f"🏷️ <b>Проект:</b> {payment['project_name']}\n\n"
        f"✅ Ваша заявка успешно оплачена!"
    )
    
    try:
        await bot.send_message(
            marketer_id,
            notification_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление маркетологу {marketer_id}: {e}")


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


def setup_financier_handlers(dp: Dispatcher):
    """Регистрация обработчиков для финансистов"""
    
    def is_financier_or_manager(message: Message) -> bool:
        role = Config.get_user_role(message.from_user.id)
        return role in ["financier", "manager"]
    
    def is_financier(message: Message) -> bool:
        return Config.get_user_role(message.from_user.id) == "financier"
    
    # Обработчик подтверждения оплаты
    dp.message.register(
        payment_confirmation_handler,
        F.text.regexp(r"оплачено\s+\d+", flags=re.IGNORECASE),
        is_financier
    )
    
    # Обработчик подтверждения с файлами
    dp.message.register(
        payment_confirmation_handler,
        (F.document | F.photo) & F.caption.regexp(r"оплачено\s+\d+", flags=re.IGNORECASE),
        is_financier
    )
    
    # Команда баланса
    dp.message.register(
        balance_command_handler,
        Command("balance"),
        is_financier_or_manager
    ) 