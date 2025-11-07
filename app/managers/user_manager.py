"""Модуль для управления пользователями бота (Postgres)"""
from typing import Set

from app.core.db import Database


class UserManager:
    """Менеджер для работы с пользователями бота (через Postgres)"""
    
    def __init__(self):
        self.db = Database.get_instance()
    
    def add_user(self, user_id: int) -> bool:
        return self.db.users_add(user_id)
    
    def is_user_registered(self, user_id: int) -> bool:
        return self.db.users_is_registered(user_id)
    
    def get_all_users(self) -> Set[int]:
        return set(self.db.users_get_all())

    def remove_user(self, user_id: int) -> bool:
        return self.db.users_remove(user_id)


