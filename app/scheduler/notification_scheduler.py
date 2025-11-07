"""Планировщик уведомлений"""
import asyncio
import logging
from datetime import datetime
from typing import Dict

from aiogram import Bot

from app.managers.config_manager import SupplierConfigManager
from app.managers.user_manager import UserManager


logger = logging.getLogger(__name__)


class NotificationScheduler:
    def __init__(self, bot: Bot, config_manager: SupplierConfigManager, user_manager: UserManager):
        self.bot = bot
        self.config_manager = config_manager
        self.user_manager = user_manager
        self.last_check_time: Dict[str, datetime] = {}
        self.running = False

    async def start(self):
        self.running = True
        logger.info("Планировщик уведомлений запущен")
        while self.running:
            try:
                await self.check_and_send_notifications()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Ошибка в планировщике уведомлений: {e}")
                await asyncio.sleep(60)

    def stop(self):
        self.running = False
        logger.info("Планировщик уведомлений остановлен")

    def reset_notification_time(self, supplier_name: str):
        if supplier_name in self.last_check_time:
            del self.last_check_time[supplier_name]
            logger.info(f"Время последней отправки для '{supplier_name}' сброшено")

    def get_notification_time(self, supplier_name: str) -> datetime:
        return self.last_check_time.get(supplier_name)

    async def check_and_send_notifications(self):
        suppliers = self.config_manager.list_suppliers()
        current_time = datetime.now()
        logger.debug(f"Проверка уведомлений: {len(suppliers)} поставщиков, текущее время: {current_time}")
        for supplier_name in suppliers:
            config = self.config_manager.get_supplier_config(supplier_name)
            if not config:
                continue
            notification = config.get('notification')
            if not notification:
                continue
            should_send = await self.should_send_notification(supplier_name, notification, current_time)
            logger.debug(f"Поставщик '{supplier_name}': должно отправляться = {should_send}")
            if should_send:
                await self.send_notification(supplier_name)
                self.last_check_time[supplier_name] = current_time
                logger.info(f"Уведомление для '{supplier_name}' отправлено, время сохранено: {current_time}")

    async def should_send_notification(self, supplier_name: str, notification: Dict, current_time: datetime) -> bool:
        if notification.get('type') == 'days':
            interval_days = notification.get('interval', 5)
            last_time = self.last_check_time.get(supplier_name)
            logger.debug(f"Проверка дней для '{supplier_name}': интервал={interval_days}, последняя отправка={last_time}")
            if last_time is None:
                logger.info(f"Первая отправка для '{supplier_name}' (тип: дни)")
                return True
            time_diff = current_time - last_time
            return time_diff.days >= interval_days
        elif notification.get('type') == 'weeks':
            interval_weeks = notification.get('interval', 1)
            weekdays = notification.get('weekdays', [])
            current_weekday = current_time.weekday()
            logger.debug(f"Проверка недель для '{supplier_name}': интервал={interval_weeks} недель, дни недели={weekdays}, текущий день={current_weekday}")
            if current_weekday not in weekdays:
                return False
            last_time = self.last_check_time.get(supplier_name)
            if last_time is None:
                logger.info(f"Первая отправка для '{supplier_name}' (тип: недели), сегодня день недели {current_weekday}")
                return True
            time_diff = current_time - last_time
            weeks_passed = time_diff.days // 7
            same_day = last_time.date() == current_time.date()
            return weeks_passed >= interval_weeks and not same_day
        return False

    async def send_notification(self, supplier_name: str):
        users = self.user_manager.get_all_users()
        if not users:
            logger.info(f"Нет пользователей для отправки уведомления о поставщике {supplier_name}")
            return
        message_text = (
            f"🔔 Напоминание о поставщике\n\n"
            f"Поставщик: {supplier_name}\n"
            f"Не забудьте проверить наличие новых прайс-листов или заказов."
        )
        for user_id in users:
            try:
                await self.bot.send_message(user_id, message_text)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
                if "chat not found" in str(e).lower() or "blocked" in str(e).lower():
                    try:
                        self.user_manager.remove_user(user_id)
                    except Exception:
                        pass


