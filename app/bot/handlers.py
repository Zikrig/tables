from typing import Dict
import os
import logging

from aiogram import F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.main import dp, bot, config_manager, user_manager, notification_scheduler, UPLOAD_DIR, OUTPUT_DIR, ACCESS_PASSWORD
from app.excel.order_generator import OrderGenerator


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrderStates(StatesGroup):
    waiting_for_price = State()
    waiting_for_warehouse = State()
    waiting_for_preorders = State()
    waiting_for_supplier = State()
    configuring_start_row = State()
    configuring_article_col = State()
    configuring_price_col = State()
    configuring_quantity_col = State()
    configuring_sum_col = State()
    configuring_price_file = State()
    editing_start_row = State()
    editing_article_col = State()
    editing_price_col = State()
    editing_quantity_col = State()
    editing_sum_col = State()
    editing_price_file = State()
    configuring_warehouse = State()
    configuring_preorders = State()
    waiting_for_password = State()
    configuring_notification_type = State()
    configuring_notification_days = State()
    configuring_notification_weeks = State()
    configuring_notification_weekdays = State()


user_data: Dict[int, Dict] = {}


def get_user_data(user_id: int) -> Dict:
    if user_id not in user_data:
        user_data[user_id] = {
            'price_file': None,
            'warehouse_file': None,
            'preorders_file': None,
            'supplier': None,
            'config': None
        }
    return user_data[user_id]


def column_letter_to_index(column: str) -> int:
    column = column.upper().strip()
    result = 0
    for char in column:
        if not char.isalpha():
            raise ValueError("Столбец должен содержать только буквы")
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result - 1


def index_to_column_letter(index: int) -> str:
    result = ""
    index += 1
    while index > 0:
        index -= 1
        result = chr(ord('A') + index % 26) + result
        index //= 26
    return result


def row_number_to_index(row: int) -> int:
    return row - 1


def index_to_row_number(index: int) -> int:
    return index + 1


def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Управление поставщиками", callback_data="menu_suppliers")
    builder.button(text="📋 Сгенерировать заказ", callback_data="menu_generate")
    builder.button(text="📖 Справка", callback_data="menu_help")
    builder.adjust(1)
    return builder.as_markup()



@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    if not user_manager.is_user_registered(user_id):
        await message.answer(
            "🔐 Для использования бота необходимо ввести пароль доступа.\n\n"
            "Введите пароль:"
        )
        await state.set_state(OrderStates.waiting_for_password)
        return
    
    text = (
        "👋 Добро пожаловать в бота для генерации заказов!\n\n"
        "Этот бот помогает автоматически заполнять прайс-листы производителей "
        "на основе заказов на склад и предзаказов клиентов.\n\n"
        "Выберите действие:"
    )
    await message.answer(text, reply_markup=get_main_menu())


@dp.message(StateFilter(OrderStates.waiting_for_password))
async def process_password(message: Message, state: FSMContext):
    """Обработка ввода пароля"""
    user_id = message.from_user.id
    password = message.text.strip()
    
    if password == ACCESS_PASSWORD:
        user_manager.add_user(user_id)
        await message.answer(
            "✅ Пароль верный! Вы зарегистрированы.\n\n"
            "Теперь вы можете использовать бота."
        )
        await state.clear()
        
        text = (
            "👋 Добро пожаловать в бота для генерации заказов!\n\n"
            "Этот бот помогает автоматически заполнять прайс-листы производителей "
            "на основе заказов на склад и предзаказов клиентов.\n\n"
            "Выберите действие:"
        )
        await message.answer(text, reply_markup=get_main_menu())
    else:
        await message.answer("❌ Неверный пароль. Попробуйте еще раз:")


@dp.callback_query(F.data == "menu_help")
async def callback_menu_help(callback: CallbackQuery):
    """Обработчик меню справки"""
    text = (
        "📖 Справка по использованию бота:\n\n"
        "1. Используйте 'Управление поставщиками' для настройки поставщиков\n"
        "2. Используйте 'Сгенерировать заказ' для генерации заказа\n"
        "3. Загрузите три файла:\n"
        "   - Прайс-лист производителя\n"
        "   - Заказ на склад\n"
        "   - Предзаказы клиентов\n\n"
        "Бот автоматически сопоставит товары по артикулам и создаст заказ."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="menu_main")
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data == "menu_main")
async def callback_menu_main(callback: CallbackQuery):
    """Обработчик возврата в главное меню"""
    text = (
        "👋 Главное меню\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "menu_suppliers")
async def callback_menu_suppliers(callback: CallbackQuery):
    """Обработчик меню поставщиков"""
    suppliers = config_manager.list_suppliers()
    
    builder = InlineKeyboardBuilder()
    if not suppliers:
        text = "📦 Список поставщиков пуст.\n\nНажмите кнопку ниже, чтобы добавить нового поставщика."
    else:
        text = "📦 Список поставщиков:\n\n" + "\n".join(f"• {s}" for s in suppliers)
        for supplier in suppliers:
            builder.button(text=f"⚙️ {supplier}", callback_data=f"supplier_{supplier}")
    
    builder.button(text="➕ Добавить поставщика", callback_data="add_supplier")
    builder.button(text="🔙 Назад в меню", callback_data="menu_main")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data == "add_supplier")
async def callback_add_supplier(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления поставщика"""
    await callback.message.edit_text("✏️ Введите название поставщика:")
    await state.set_state(OrderStates.waiting_for_supplier)
    await callback.answer()


@dp.message(StateFilter(OrderStates.waiting_for_supplier))
async def process_supplier_name(message: Message, state: FSMContext):
    """Обработка названия поставщика"""
    supplier_name = message.text.strip()
    
    if not supplier_name:
        await message.answer("❌ Название не может быть пустым. Попробуйте еще раз:")
        return
    
    # Сохраняем название в состоянии
    await state.update_data(supplier_name=supplier_name)
    
    # Начинаем настройку разметки
    await message.answer(
        f"✅ Название поставщика: {supplier_name}\n\n"
        f"📋 Теперь настроим разметку прайс-листа.\n\n"
        f"Введите номер строки начала таблицы (начиная с 1):\n"
        f"Пример: 3 (если данные начинаются с 3-й строки)"
    )
    await state.set_state(OrderStates.configuring_start_row)


@dp.message(StateFilter(OrderStates.configuring_start_row))
async def process_start_row(message: Message, state: FSMContext):
    """Обработка строки начала таблицы"""
    try:
        start_row = int(message.text.strip())
        if start_row < 1:
            raise ValueError("Строка не может быть меньше 1")
        # Конвертируем в индекс (строка 1 -> индекс 0)
        start_row_index = row_number_to_index(start_row)
        await state.update_data(start_row=start_row_index, start_row_display=start_row)
        await message.answer(
            f"✅ Начало строки: {start_row}\n\n"
            f"Введите букву столбца с артикулом (A, B, C...):\n"
            f"Пример: A (если артикул в 1-м столбце)"
        )
        await state.set_state(OrderStates.configuring_article_col)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите целое число начиная с 1 (например: 3)")


# Обработка start_col больше не используется


@dp.message(StateFilter(OrderStates.configuring_article_col))
async def process_article_col(message: Message, state: FSMContext):
    """Обработка столбца артикула"""
    try:
        article_col_letter = message.text.strip().upper()
        if not article_col_letter or not article_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        # Конвертируем в индекс
        article_col_index = column_letter_to_index(article_col_letter)
        await state.update_data(article_col=article_col_index, article_col_display=article_col_letter)
        await message.answer(
            f"✅ Столбец артикула: {article_col_letter}\n\n"
            f"Введите букву столбца с ценой (A, B, C...):\n"
            f"Пример: E (если цена в 5-м столбце)"
        )
        await state.set_state(OrderStates.configuring_price_col)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: A)")


@dp.message(StateFilter(OrderStates.configuring_price_col))
async def process_price_col(message: Message, state: FSMContext):
    """Обработка столбца цены"""
    try:
        price_col_letter = message.text.strip().upper()
        if not price_col_letter or not price_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        # Конвертируем в индекс
        price_col_index = column_letter_to_index(price_col_letter)
        await state.update_data(price_col=price_col_index, price_col_display=price_col_letter)
        await message.answer(
            f"✅ Столбец цены: {price_col_letter}\n\n"
            f"Введите букву столбца для количества (A, B, C...):\n"
            f"Пример: J (если количество в 10-м столбце)"
        )
        await state.set_state(OrderStates.configuring_quantity_col)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: E)")


@dp.message(StateFilter(OrderStates.configuring_quantity_col))
async def process_quantity_col(message: Message, state: FSMContext):
    """Обработка столбца количества"""
    try:
        quantity_col_letter = message.text.strip().upper()
        if not quantity_col_letter or not quantity_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        # Конвертируем в индекс
        quantity_col_index = column_letter_to_index(quantity_col_letter)
        await state.update_data(quantity_col=quantity_col_index, quantity_col_display=quantity_col_letter)
        await message.answer(
            f"✅ Столбец количества: {quantity_col_letter}\n\n"
            f"Введите букву столбца для суммы (A, B, C...):\n"
            f"Пример: K (если сумма в 11-м столбце)"
        )
        await state.set_state(OrderStates.configuring_sum_col)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: J)")


@dp.message(StateFilter(OrderStates.configuring_sum_col))
async def process_sum_col(message: Message, state: FSMContext):
    """Обработка столбца суммы"""
    try:
        sum_col_letter = message.text.strip().upper()
        if not sum_col_letter or not sum_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        # Конвертируем в индекс
        sum_col_index = column_letter_to_index(sum_col_letter)
        await state.update_data(sum_col=sum_col_index, sum_col_display=sum_col_letter)
        
        data = await state.get_data()
        supplier_name = data['supplier_name']
        
        await message.answer(
            f"✅ Столбец суммы: {sum_col_letter}\n\n"
            f"📄 Теперь загрузите полный прайс-лист производителя (только .xlsx)."
        )
        await state.set_state(OrderStates.configuring_price_file)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: K)")


# Обработка строки ИТОГО и подсчёта количества удалены (не используются)


@dp.message(StateFilter(OrderStates.configuring_price_file), F.document)
async def process_configuring_price_file(message: Message, state: FSMContext):
    """Обработка загрузки прайс-листа при настройке поставщика"""
    user_id = message.from_user.id
    
    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте файл Excel")
        return
    
    # Проверяем расширение файла
    file_name = message.document.file_name or ""
    if not file_name.lower().endswith('.xlsx'):
        await message.answer("❌ Пожалуйста, отправьте файл Excel в формате .xlsx")
        return
    
    try:
        file = await bot.get_file(message.document.file_id)
        tmp_path = UPLOAD_DIR / f"suppliers_{user_id}_{file.file_id}.xlsx"
        await bot.download_file(file.file_path, tmp_path)
        price_source_path = tmp_path
        
        # Получаем все данные из состояния
        data = await state.get_data()
        supplier_name = data['supplier_name']
        
        # Создаем конфигурацию
        config = {
            'price_list': {
                'start_row': data.get('start_row', 1),  # Индекс
                'article_col': data.get('article_col', 0),
                'price_col': data.get('price_col', 4),
                'quantity_col': data.get('quantity_col', 9),
                'sum_col': data.get('sum_col', 10),
            },
            'warehouse_order': {
                'article_col': 0,
                'quantity_col': 4,
                'start_row': 1,
            },
            'preorders': {
                'article_col': 2,
                'article_col2': 5,
                'quantity_col': 4,
                'start_row': 1,
            },
            'price_file': str(price_source_path),
            'price_template': str(tmp_path)
        }
        
        # Сохраняем конфигурацию
        config_manager.set_supplier_config(supplier_name, config)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📦 К списку поставщиков", callback_data="menu_suppliers")
        builder.button(text="🔙 В главное меню", callback_data="menu_main")
        
        # Получаем отображаемые значения
        start_row_display = data.get('start_row_display', index_to_row_number(data.get('start_row', 1)))
        article_col_display = data.get('article_col_display', index_to_column_letter(data.get('article_col', 0)))
        price_col_display = data.get('price_col_display', index_to_column_letter(data.get('price_col', 4)))
        quantity_col_display = data.get('quantity_col_display', index_to_column_letter(data.get('quantity_col', 9)))
        sum_col_display = data.get('sum_col_display', index_to_column_letter(data.get('sum_col', 10)))
        
        await message.answer(
            f"✅ Поставщик '{supplier_name}' успешно добавлен и настроен!\n\n"
            f"📋 Разметка:\n"
            f"  • Начало таблицы: строка {start_row_display}\n"
            f"  • Артикул: столбец {article_col_display}\n"
            f"  • Цена: столбец {price_col_display}\n"
            f"  • Количество: столбец {quantity_col_display}\n"
            f"  • Сумма: столбец {sum_col_display}\n"
            f"  • Прайс-лист: загружен",
            reply_markup=builder.as_markup()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке прайс-листа: {e}")
        await message.answer(f"❌ Ошибка при загрузке файла: {str(e)}")


@dp.message(StateFilter(OrderStates.editing_price_file), ~F.document)
async def process_editing_price_file_text(message: Message):
    """Обработка текстового сообщения вместо прайс-листа"""
    await message.answer("❌ Пожалуйста, отправьте файл Excel в формате .xlsx")


@dp.callback_query(F.data == "menu_generate")
async def callback_menu_generate(callback: CallbackQuery):
    """Обработчик меню генерации заказа"""
    suppliers = config_manager.list_suppliers()
    
    if not suppliers:
        builder = InlineKeyboardBuilder()
        builder.button(text="📦 Добавить поставщика", callback_data="add_supplier")
        builder.button(text="🔙 Назад в меню", callback_data="menu_main")
        await callback.message.edit_text(
            "❌ Нет настроенных поставщиков.\n\n"
            "Сначала добавьте поставщика, чтобы можно было сгенерировать заказ.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for supplier in suppliers:
        builder.button(text=supplier, callback_data=f"select_supplier_{supplier}")
    builder.button(text="🔙 Назад в меню", callback_data="menu_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📋 Выберите поставщика для генерации заказа:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("select_supplier_"))
async def callback_select_supplier(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора поставщика"""
    supplier_name = callback.data.replace("select_supplier_", "")
    user_id = callback.from_user.id
    
    data = get_user_data(user_id)
    data['supplier'] = supplier_name
    config = config_manager.get_supplier_config(supplier_name)
    data['config'] = config
    
    # Проверяем, есть ли сохраненный прайс-лист
    saved_price_file = config.get('price_file')
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить", callback_data="cancel_order")
    
    if saved_price_file and os.path.exists(saved_price_file):
        # Используем сохраненный прайс-лист
        data['price_file'] = saved_price_file
        builder = InlineKeyboardBuilder()
        builder.button(text="📄 Использовать сохраненный", callback_data="use_saved_price")
        builder.button(text="🔄 Заменить прайс-лист", callback_data="replace_price")
        builder.button(text="❌ Отменить", callback_data="cancel_order")
        builder.adjust(1)
        
        await callback.message.edit_text(
            f"✅ Выбран поставщик: {supplier_name}\n\n"
            f"📄 У поставщика есть сохраненный прайс-лист.\n"
            f"Выберите действие:",
            reply_markup=builder.as_markup()
        )
        await callback.answer(f"Выбран поставщик: {supplier_name}")
    else:
        # Запрашиваем прайс-лист
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отменить", callback_data="cancel_order")
        await callback.message.edit_text(
            f"✅ Выбран поставщик: {supplier_name}\n\n"
            f"📤 Загрузите прайс-лист производителя (Excel файл):",
            reply_markup=builder.as_markup()
        )
        await state.set_state(OrderStates.waiting_for_price)
        await callback.answer(f"Выбран поставщик: {supplier_name}")


@dp.callback_query(F.data == "use_saved_price")
async def callback_use_saved_price(callback: CallbackQuery, state: FSMContext):
    """Обработчик использования сохраненного прайс-листа"""
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    
    supplier_name = data['supplier']
    config = config_manager.get_supplier_config(supplier_name)
    saved_price_file = config.get('price_file')
    
    if saved_price_file and os.path.exists(saved_price_file):
        data['price_file'] = saved_price_file
        
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отменить", callback_data="cancel_order")
        
        await callback.message.edit_text(
            f"✅ Используется сохраненный прайс-лист\n\n"
            f"📤 Загрузите файл 'Заказ на склад' (Excel файл):",
            reply_markup=builder.as_markup()
        )
        await state.set_state(OrderStates.waiting_for_warehouse)
        await callback.answer()
    else:
        await callback.answer("❌ Сохраненный прайс-лист не найден", show_alert=True)


@dp.callback_query(F.data == "replace_price")
async def callback_replace_price(callback: CallbackQuery, state: FSMContext):
    """Обработчик замены прайс-листа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить", callback_data="cancel_order")
    
    await callback.message.edit_text(
        "📤 Загрузите новый прайс-лист производителя (Excel файл):",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OrderStates.waiting_for_price)
    await callback.answer()


@dp.callback_query(F.data.startswith("supplier_"))
async def callback_supplier_details(callback: CallbackQuery):
    """Обработчик просмотра поставщика"""
    supplier_name = callback.data.replace("supplier_", "")
    config = config_manager.get_supplier_config(supplier_name)
    
    if not config:
        await callback.answer("❌ Конфигурация не найдена", show_alert=True)
        return
    
    price_list = config['price_list']
    # Конвертируем индексы обратно в отображаемые значения
    start_row_display = index_to_row_number(price_list.get('start_row', 1))
    article_col_display = index_to_column_letter(price_list.get('article_col', 0))
    price_col_display = index_to_column_letter(price_list.get('price_col', 4))
    quantity_col_display = index_to_column_letter(price_list.get('quantity_col', 9))
    sum_col_display = index_to_column_letter(price_list.get('sum_col', 10))
    
    text = (
        f"⚙️ Поставщик: {supplier_name}\n\n"
        f"📋 Прайс-лист:\n"
        f"  • Начало таблицы: строка {start_row_display}\n"
        f"  • Столбец артикула: {article_col_display}\n"
        f"  • Столбец цены: {price_col_display}\n"
        f"  • Столбец количества: {quantity_col_display}\n"
        f"  • Столбец суммы: {sum_col_display}\n"
        f"  • Прайс-лист: {'загружен' if config.get('price_file') else 'не загружен'}\n\n"
        f"📦 Заказ на склад:\n"
        f"  • Столбец артикула: {index_to_column_letter(config['warehouse_order']['article_col'])}\n"
        f"  • Столбец количества: {index_to_column_letter(config['warehouse_order']['quantity_col'])}\n"
        f"  • Начало данных: строка {index_to_row_number(config['warehouse_order']['start_row'])}\n\n"
        f"🛒 Предзаказы:\n"
        f"  • Столбец артикула 1: {index_to_column_letter(config['preorders']['article_col'])}\n"
        f"  • Столбец артикула 2: {index_to_column_letter(config['preorders']['article_col2'])}\n"
        f"  • Столбец количества: {index_to_column_letter(config['preorders']['quantity_col'])}\n"
        f"  • Начало данных: строка {index_to_row_number(config['preorders']['start_row'])}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"edit_supplier_{supplier_name}")
    builder.button(text="🔔 Настроить уведомления", callback_data=f"notifications_{supplier_name}")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_supplier_{supplier_name}")
    builder.button(text="🔙 Назад", callback_data="menu_suppliers")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data.startswith("notifications_"))
async def callback_notifications(callback: CallbackQuery, state: FSMContext):
    """Обработчик настройки уведомлений"""
    supplier_name = callback.data.replace("notifications_", "")
    config = config_manager.get_supplier_config(supplier_name)
    
    if not config:
        await callback.answer("❌ Конфигурация не найдена", show_alert=True)
        return
    
    await state.update_data(notification_supplier=supplier_name)
    
    notification = config.get('notification')
    
    if notification:
        # Уведомление уже настроено
        notification_text = (
            f"🔔 Текущие настройки уведомлений для поставщика '{supplier_name}':\n\n"
        )
        
        if notification.get('type') == 'days':
            notification_text += f"Тип: Каждые {notification.get('interval')} дней"
        elif notification.get('type') == 'weeks':
            notification_text += f"Тип: Каждые {notification.get('interval')} недель\n"
            weekdays = notification.get('weekdays', [])
            weekdays_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            selected_days = [weekdays_names[i] for i in weekdays]
            notification_text += f"Дни недели: {', '.join(selected_days)}"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Изменить уведомление", callback_data=f"edit_notification_{supplier_name}")
        builder.button(text="🔙 Назад", callback_data=f"supplier_{supplier_name}")
        builder.adjust(1)
        
        await callback.message.edit_text(notification_text, reply_markup=builder.as_markup())
    else:
        # Уведомление не настроено
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить уведомление", callback_data=f"add_notification_{supplier_name}")
        builder.button(text="🔙 Назад", callback_data=f"supplier_{supplier_name}")
        builder.adjust(1)
        
        await callback.message.edit_text(
            f"🔔 Уведомления для поставщика '{supplier_name}' не настроены.\n\n"
            f"Вы можете настроить автоматическую рассылку уведомлений всем пользователям бота.",
            reply_markup=builder.as_markup()
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("add_notification_"))
async def callback_add_notification(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления уведомления"""
    supplier_name = callback.data.replace("add_notification_", "")
    await state.update_data(notification_supplier=supplier_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 По дням (5, 10, 15, 30 дней)", callback_data="notif_type_days")
    builder.button(text="📆 По неделям (1, 2, 4, 6 недель)", callback_data="notif_type_weeks")
    builder.button(text="🔙 Назад", callback_data=f"notifications_{supplier_name}")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🔔 Настройка уведомлений\n\n"
        "Выберите тип интервала для уведомлений:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_notification_"))
async def callback_edit_notification(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования уведомления"""
    supplier_name = callback.data.replace("edit_notification_", "")
    await state.update_data(notification_supplier=supplier_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 По дням (5, 10, 15, 30 дней)", callback_data="notif_type_days")
    builder.button(text="📆 По неделям (1, 2, 4, 6 недель)", callback_data="notif_type_weeks")
    builder.button(text="🔙 Назад", callback_data=f"notifications_{supplier_name}")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🔔 Изменение уведомлений\n\n"
        "Выберите тип интервала для уведомлений:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data == "notif_type_days")
async def callback_notif_type_days(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа уведомлений - дни"""
    await state.update_data(notification_type='days')
    
    builder = InlineKeyboardBuilder()
    builder.button(text="5 дней", callback_data="notif_days_5")
    builder.button(text="10 дней", callback_data="notif_days_10")
    builder.button(text="15 дней", callback_data="notif_days_15")
    builder.button(text="30 дней", callback_data="notif_days_30")
    builder.button(text="🔙 Назад", callback_data="notif_type_back")
    builder.adjust(2)
    
    await callback.message.edit_text(
        "📅 Выберите интервал в днях:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data == "notif_type_weeks")
async def callback_notif_type_weeks(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа уведомлений - недели"""
    await state.update_data(notification_type='weeks')
    
    builder = InlineKeyboardBuilder()
    builder.button(text="1 неделя", callback_data="notif_weeks_1")
    builder.button(text="2 недели", callback_data="notif_weeks_2")
    builder.button(text="4 недели", callback_data="notif_weeks_4")
    builder.button(text="6 недель", callback_data="notif_weeks_6")
    builder.button(text="🔙 Назад", callback_data="notif_type_back")
    builder.adjust(2)
    
    await callback.message.edit_text(
        "📆 Выберите интервал в неделях:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("notif_days_"))
async def callback_notif_days(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора количества дней"""
    days = int(callback.data.replace("notif_days_", ""))
    await state.update_data(notification_interval=days)
    
    data = await state.get_data()
    supplier_name = data['notification_supplier']
    
    config = config_manager.get_supplier_config(supplier_name)
    if not config:
        await callback.answer("❌ Конфигурация не найдена", show_alert=True)
        return
    
    # Сохраняем настройки уведомления
    config['notification'] = {
        'type': 'days',
        'interval': days
    }
    config_manager.set_supplier_config(supplier_name, config)
    
    # Сбрасываем время последней отправки, чтобы первое уведомление отправилось сразу
    if notification_scheduler:
        notification_scheduler.reset_notification_time(supplier_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к поставщику", callback_data=f"supplier_{supplier_name}")
    
    await callback.message.edit_text(
        f"✅ Уведомления настроены!\n\n"
        f"Поставщик: {supplier_name}\n"
        f"Интервал: каждые {days} дней\n\n"
        f"Уведомления будут рассылаться всем пользователям бота.\n\n"
        f"Первое уведомление будет отправлено в течение минуты.",
        reply_markup=builder.as_markup()
    )
    
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data.startswith("notif_weeks_"))
async def callback_notif_weeks(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора количества недель"""
    weeks = int(callback.data.replace("notif_weeks_", ""))
    await state.update_data(notification_interval=weeks)
    
    # Предзаполняем выбранные дни из текущей конфигурации, если есть
    data = await state.get_data()
    supplier_name = data.get('notification_supplier')
    existing = None
    if supplier_name:
        cfg = config_manager.get_supplier_config(supplier_name)
        if cfg and cfg.get('notification', {}).get('type') == 'weeks':
            existing = cfg['notification'].get('weekdays', [])
    if existing:
        await state.update_data(notification_weekdays=existing)

    # Клавиатура с галочками
    data = await state.get_data()
    selected = set(data.get('notification_weekdays', []))
    weekdays_labels = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    builder = InlineKeyboardBuilder()
    for idx, label in enumerate(weekdays_labels):
        mark = "✅ " if idx in selected else ""
        builder.button(text=f"{mark}{label}", callback_data=f"notif_weekday_{idx}")
    builder.button(text="✅ Готово", callback_data="notif_weekdays_done")
    builder.adjust(2)
    
    # Текст с уже выбранными днями
    selected_names = [weekdays_labels[i] for i in sorted(selected)]
    selected_text = f"\n\nВыбрано: {', '.join(selected_names)}" if selected_names else "\n\nНичего не выбрано"
    await callback.message.edit_text(
        f"📆 Выбрано: каждые {weeks} недель\n\n"
        f"Выберите дни недели для отправки уведомлений (можно несколько):"
        f"{selected_text}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("notif_weekday_"))
async def callback_notif_weekday(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора дня недели"""
    weekday = int(callback.data.replace("notif_weekday_", ""))
    
    data = await state.get_data()
    weekdays = data.get('notification_weekdays', [])
    
    if weekday in weekdays:
        weekdays.remove(weekday)
    else:
        weekdays.append(weekday)
    
    await state.update_data(notification_weekdays=weekdays)
    
    weekdays_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    selected_names = [weekdays_names[i] for i in sorted(weekdays)]
    
    builder = InlineKeyboardBuilder()
    for idx, label in enumerate(['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье']):
        mark = "✅ " if idx in weekdays else ""
        builder.button(text=f"{mark}{label}", callback_data=f"notif_weekday_{idx}")
    builder.button(text="✅ Готово", callback_data="notif_weekdays_done")
    builder.adjust(2)
    
    interval = data.get('notification_interval', 1)
    selected_text = f"\n\nВыбрано: {', '.join(selected_names)}" if selected_names else "\n\nНичего не выбрано"
    
    await callback.message.edit_text(
        f"📆 Выбрано: каждые {interval} недель\n"
        f"Выберите дни недели для отправки уведомлений (можно несколько):"
        f"{selected_text}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data == "notif_weekdays_done")
async def callback_notif_weekdays_done(callback: CallbackQuery, state: FSMContext):
    """Обработчик завершения выбора дней недели"""
    data = await state.get_data()
    supplier_name = data['notification_supplier']
    interval = data.get('notification_interval', 1)
    weekdays = data.get('notification_weekdays', [])
    
    if not weekdays:
        # Если ничего не выбрано — отключаем уведомления
        config = config_manager.get_supplier_config(supplier_name)
        if not config:
            await callback.answer("❌ Конфигурация не найдена", show_alert=True)
            return
        if 'notification' in config:
            del config['notification']
            config_manager.set_supplier_config(supplier_name, config)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад к поставщику", callback_data=f"supplier_{supplier_name}")
        await callback.message.edit_text(
            f"🚫 Уведомления отключены для поставщика: {supplier_name}",
            reply_markup=builder.as_markup()
        )
        await state.clear()
        await callback.answer()
        return
    
    config = config_manager.get_supplier_config(supplier_name)
    if not config:
        await callback.answer("❌ Конфигурация не найдена", show_alert=True)
        return
    
    # Сохраняем настройки уведомления
    config['notification'] = {
        'type': 'weeks',
        'interval': interval,
        'weekdays': sorted(weekdays)
    }
    config_manager.set_supplier_config(supplier_name, config)
    
    # Сбрасываем время последней отправки, чтобы первое уведомление отправилось сразу
    if notification_scheduler:
        notification_scheduler.reset_notification_time(supplier_name)
    
    weekdays_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    selected_names = [weekdays_names[i] for i in sorted(weekdays)]
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к поставщику", callback_data=f"supplier_{supplier_name}")
    
    await callback.message.edit_text(
        f"✅ Уведомления настроены!\n\n"
        f"Поставщик: {supplier_name}\n"
        f"Интервал: каждые {interval} недель\n"
        f"Дни недели: {', '.join(selected_names)}\n\n"
        f"Уведомления будут рассылаться всем пользователям бота.\n\n"
        f"⚠️ Если сегодня выбранный день недели, первое уведомление будет отправлено в течение минуты.",
        reply_markup=builder.as_markup()
    )
    
    await state.clear()
    await callback.answer()




@dp.callback_query(F.data == "notif_type_back")
async def callback_notif_type_back(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата к выбору типа уведомлений"""
    data = await state.get_data()
    supplier_name = data.get('notification_supplier')
    
    if supplier_name:
        await callback_notifications(callback, state)
    else:
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("edit_supplier_"))
async def callback_edit_supplier(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования поставщика"""
    supplier_name = callback.data.replace("edit_supplier_", "")
    config = config_manager.get_supplier_config(supplier_name)
    
    if not config:
        await callback.answer("❌ Конфигурация не найдена", show_alert=True)
        return
    
    await state.update_data(editing_supplier=supplier_name)
    
    price_list = config['price_list']
    start_row_display = index_to_row_number(price_list.get('start_row', 1))
    article_col_display = index_to_column_letter(price_list.get('article_col', 0))
    price_col_display = index_to_column_letter(price_list.get('price_col', 4))
    quantity_col_display = index_to_column_letter(price_list.get('quantity_col', 9))
    sum_col_display = index_to_column_letter(price_list.get('sum_col', 10))
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📏 Начало: строка {start_row_display}", 
                   callback_data=f"edit_param_start_{supplier_name}")
    builder.button(text=f"🏷️ Артикул: столбец {article_col_display}", 
                   callback_data=f"edit_param_article_{supplier_name}")
    builder.button(text=f"💰 Цена: столбец {price_col_display}", 
                   callback_data=f"edit_param_price_{supplier_name}")
    builder.button(text=f"📦 Количество: столбец {quantity_col_display}", 
                   callback_data=f"edit_param_quantity_{supplier_name}")
    builder.button(text=f"💵 Сумма: столбец {sum_col_display}", 
                   callback_data=f"edit_param_sum_{supplier_name}")
    builder.button(text="📄 Прайс-лист", 
                   callback_data=f"edit_price_file_{supplier_name}")
    builder.button(text="🔙 Назад", callback_data=f"supplier_{supplier_name}")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"✏️ Редактирование поставщика: {supplier_name}\n\n"
        f"Выберите параметр для редактирования:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_param_start_"))
async def callback_edit_start(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования начала таблицы"""
    supplier_name = callback.data.replace("edit_param_start_", "")
    await state.update_data(editing_supplier=supplier_name, editing_param="start")
    await callback.message.edit_text(
        "✏️ Редактирование начала таблицы\n\n"
        "Введите номер строки начала таблицы (начиная с 1):\n"
        "Пример: 3"
    )
    await state.set_state(OrderStates.editing_start_row)
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_param_article_"))
async def callback_edit_article(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования столбца артикула"""
    supplier_name = callback.data.replace("edit_param_article_", "")
    await state.update_data(editing_supplier=supplier_name, editing_param="article")
    await callback.message.edit_text(
        "✏️ Редактирование столбца артикула\n\n"
        "Введите букву столбца с артикулом (A, B, C...):\n"
        "Пример: A"
    )
    await state.set_state(OrderStates.editing_article_col)
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_param_price_"))
async def callback_edit_price(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования столбца цены"""
    supplier_name = callback.data.replace("edit_param_price_", "")
    await state.update_data(editing_supplier=supplier_name, editing_param="price")
    await callback.message.edit_text(
        "✏️ Редактирование столбца цены\n\n"
        "Введите букву столбца с ценой (A, B, C...):\n"
        "Пример: E"
    )
    await state.set_state(OrderStates.editing_price_col)
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_param_quantity_"))
async def callback_edit_quantity(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования столбца количества"""
    supplier_name = callback.data.replace("edit_param_quantity_", "")
    await state.update_data(editing_supplier=supplier_name, editing_param="quantity")
    await callback.message.edit_text(
        "✏️ Редактирование столбца количества\n\n"
        "Введите букву столбца для количества (A, B, C...):\n"
        "Пример: J"
    )
    await state.set_state(OrderStates.editing_quantity_col)
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_param_sum_"))
async def callback_edit_sum(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования столбца суммы"""
    supplier_name = callback.data.replace("edit_param_sum_", "")
    await state.update_data(editing_supplier=supplier_name, editing_param="sum")
    await callback.message.edit_text(
        "✏️ Редактирование столбца суммы\n\n"
        "Введите букву столбца для суммы (A, B, C...):\n"
        "Пример: K"
    )
    await state.set_state(OrderStates.editing_sum_col)
    await callback.answer()


# Обработчик редактирования строки ИТОГО удалён


@dp.callback_query(F.data.startswith("edit_price_file_"))
async def callback_edit_price_file(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования прайс-листа"""
    supplier_name = callback.data.replace("edit_price_file_", "")
    await state.update_data(editing_supplier=supplier_name, editing_param="price_file")
    await callback.message.edit_text(
        "✏️ Редактирование прайс-листа\n\n"
        "Загрузите новый прайс-лист (Excel файл):"
    )
    await state.set_state(OrderStates.editing_price_file)
    await callback.answer()


@dp.callback_query(F.data == "cancel_order")
async def callback_cancel_order(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены заказа"""
    user_id = callback.from_user.id
    user_data[user_id] = {
        'price_file': None,
        'warehouse_file': None,
        'preorders_file': None,
        'supplier': None,
        'config': None
    }
    await state.clear()
    await callback.message.edit_text(
        "❌ Заказ отменен.",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_supplier_"))
async def callback_delete_supplier(callback: CallbackQuery):
    """Обработчик удаления поставщика"""
    supplier_name = callback.data.replace("delete_supplier_", "")
    config_manager.delete_supplier(supplier_name)
    
    await callback.answer(f"✅ Поставщик '{supplier_name}' удален", show_alert=True)
    
    # Обновляем список поставщиков
    suppliers = config_manager.list_suppliers()
    
    builder = InlineKeyboardBuilder()
    if not suppliers:
        text = "📦 Список поставщиков пуст.\n\nНажмите кнопку ниже, чтобы добавить нового поставщика."
    else:
        text = "📦 Список поставщиков:\n\n" + "\n".join(f"• {s}" for s in suppliers)
        for supplier in suppliers:
            builder.button(text=f"⚙️ {supplier}", callback_data=f"supplier_{supplier}")
    
    builder.button(text="➕ Добавить поставщика", callback_data="add_supplier")
    builder.button(text="🔙 Назад в меню", callback_data="menu_main")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@dp.message(StateFilter(OrderStates.editing_start_row))
async def process_editing_start_row(message: Message, state: FSMContext):
    """Обработка редактирования строки начала таблицы"""
    try:
        start_row = int(message.text.strip())
        if start_row < 1:
            raise ValueError("Строка не может быть меньше 1")
        data = await state.get_data()
        supplier_name = data['editing_supplier']
        
        config = config_manager.get_supplier_config(supplier_name)
        if not config:
            await message.answer("❌ Конфигурация не найдена")
            await state.clear()
            return
        
        config['price_list']['start_row'] = row_number_to_index(start_row)
        config_manager.set_supplier_config(supplier_name, config)
        
        await finish_editing(message, state, supplier_name, f"Начало таблицы: строка {start_row}")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите целое число начиная с 1 (например: 3)")


# Обработчик редактирования столбца начала таблицы удалён (не используется)


@dp.message(StateFilter(OrderStates.editing_article_col))
async def process_editing_article_col(message: Message, state: FSMContext):
    """Обработка редактирования столбца артикула"""
    try:
        if not message.text:
            await message.answer("❌ Пожалуйста, введите букву столбца (например: A)")
            return
        article_col_letter = message.text.strip().upper()
        if not article_col_letter or not article_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        data = await state.get_data()
        supplier_name = data['editing_supplier']
        
        config = config_manager.get_supplier_config(supplier_name)
        if not config:
            await message.answer("❌ Конфигурация не найдена")
            await state.clear()
            return
        
        config['price_list']['article_col'] = column_letter_to_index(article_col_letter)
        config_manager.set_supplier_config(supplier_name, config)
        
        await finish_editing(message, state, supplier_name, f"Столбец артикула: {article_col_letter}")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: A)")


@dp.message(StateFilter(OrderStates.editing_price_col))
async def process_editing_price_col(message: Message, state: FSMContext):
    """Обработка редактирования столбца цены"""
    try:
        if not message.text:
            await message.answer("❌ Пожалуйста, введите букву столбца (например: E)")
            return
        price_col_letter = message.text.strip().upper()
        if not price_col_letter or not price_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        data = await state.get_data()
        supplier_name = data['editing_supplier']
        
        config = config_manager.get_supplier_config(supplier_name)
        if not config:
            await message.answer("❌ Конфигурация не найдена")
            await state.clear()
            return
        
        config['price_list']['price_col'] = column_letter_to_index(price_col_letter)
        config_manager.set_supplier_config(supplier_name, config)
        
        await finish_editing(message, state, supplier_name, f"Столбец цены: {price_col_letter}")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: E)")


@dp.message(StateFilter(OrderStates.editing_quantity_col))
async def process_editing_quantity_col(message: Message, state: FSMContext):
    """Обработка редактирования столбца количества"""
    try:
        if not message.text:
            await message.answer("❌ Пожалуйста, введите букву столбца (например: J)")
            return
        quantity_col_letter = message.text.strip().upper()
        if not quantity_col_letter or not quantity_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        data = await state.get_data()
        supplier_name = data['editing_supplier']
        
        config = config_manager.get_supplier_config(supplier_name)
        if not config:
            await message.answer("❌ Конфигурация не найдена")
            await state.clear()
            return
        
        config['price_list']['quantity_col'] = column_letter_to_index(quantity_col_letter)
        config_manager.set_supplier_config(supplier_name, config)
        
        await finish_editing(message, state, supplier_name, f"Столбец количества: {quantity_col_letter}")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: J)")


@dp.message(StateFilter(OrderStates.editing_sum_col))
async def process_editing_sum_col(message: Message, state: FSMContext):
    """Обработка редактирования столбца суммы"""
    try:
        if not message.text:
            await message.answer("❌ Пожалуйста, введите букву столбца (например: K)")
            return
        sum_col_letter = message.text.strip().upper()
        if not sum_col_letter or not sum_col_letter.isalpha():
            raise ValueError("Некорректная буква столбца")
        data = await state.get_data()
        supplier_name = data['editing_supplier']
        
        config = config_manager.get_supplier_config(supplier_name)
        if not config:
            await message.answer("❌ Конфигурация не найдена")
            await state.clear()
            return
        
        config['price_list']['sum_col'] = column_letter_to_index(sum_col_letter)
        config_manager.set_supplier_config(supplier_name, config)
        
        await finish_editing(message, state, supplier_name, f"Столбец суммы: {sum_col_letter}")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите букву столбца (например: K)")


# Редактирование строки ИТОГО удалено (итоги не используются)


# Переключатель подсчёта количества в ИТОГО удалён


# Редактирование опции подсчёта количества в ИТОГО удалено


@dp.message(StateFilter(OrderStates.editing_price_file), F.document)
async def process_editing_price_file(message: Message, state: FSMContext):
    """Обработка редактирования прайс-листа"""
    user_id = message.from_user.id
    data = await state.get_data()
    supplier_name = data['editing_supplier']
    
    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте файл Excel")
        return
    
    file_name = message.document.file_name or ""
    if not file_name.lower().endswith('.xlsx'):
        await message.answer("❌ Пожалуйста, отправьте файл Excel в формате .xlsx")
        return
    
    try:
        file = await bot.get_file(message.document.file_id)
        tmp_path = UPLOAD_DIR / f"suppliers_{user_id}_{file.file_id}.xlsx"
        await bot.download_file(file.file_path, tmp_path)
        new_price_file = tmp_path
        
        config = config_manager.get_supplier_config(supplier_name)
        if not config:
            await message.answer("❌ Конфигурация не найдена")
            await state.clear()
            return
        
        config['price_file'] = str(new_price_file)
        config['price_template'] = str(tmp_path)
        config_manager.set_supplier_config(supplier_name, config)
        
        await finish_editing(message, state, supplier_name, "Прайс-лист: обновлен")
    except Exception as e:
        logger.error(f"Ошибка при загрузке прайс-листа: {e}")
        await message.answer(f"❌ Ошибка при загрузке файла: {str(e)}")


async def finish_editing(message: Message, state: FSMContext, supplier_name: str, changed_param: str):
    """Завершает редактирование и возвращает к деталям поставщика"""
    config = config_manager.get_supplier_config(supplier_name)
    price_list = config['price_list']
    
    start_row_display = index_to_row_number(price_list.get('start_row', 1))
    article_col_display = index_to_column_letter(price_list.get('article_col', 0))
    price_col_display = index_to_column_letter(price_list.get('price_col', 4))
    quantity_col_display = index_to_column_letter(price_list.get('quantity_col', 9))
    sum_col_display = index_to_column_letter(price_list.get('sum_col', 10))
    
    text = (
        f"⚙️ Поставщик: {supplier_name}\n\n"
        f"📋 Прайс-лист:\n"
        f"  • Начало таблицы: строка {start_row_display}\n"
        f"  • Столбец артикула: {article_col_display}\n"
        f"  • Столбец цены: {price_col_display}\n"
        f"  • Столбец количества: {quantity_col_display}\n"
        f"  • Столбец суммы: {sum_col_display}\n"
        f"  • Прайс-лист: {'загружен' if config.get('price_file') else 'не загружен'}\n\n"
        f"📦 Заказ на склад:\n"
        f"  • Столбец артикула: {index_to_column_letter(config['warehouse_order']['article_col'])}\n"
        f"  • Столбец количества: {index_to_column_letter(config['warehouse_order']['quantity_col'])}\n"
        f"  • Начало данных: строка {index_to_row_number(config['warehouse_order']['start_row'])}\n\n"
        f"🛒 Предзаказы:\n"
        f"  • Столбец артикула 1: {index_to_column_letter(config['preorders']['article_col'])}\n"
        f"  • Столбец артикула 2: {index_to_column_letter(config['preorders']['article_col2'])}\n"
        f"  • Столбец количества: {index_to_column_letter(config['preorders']['quantity_col'])}\n"
        f"  • Начало данных: строка {index_to_row_number(config['preorders']['start_row'])}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"edit_supplier_{supplier_name}")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_supplier_{supplier_name}")
    builder.button(text="🔙 Назад", callback_data="menu_suppliers")
    builder.adjust(1)
    
    await message.answer(f"✅ {changed_param}")
    await message.answer(text, reply_markup=builder.as_markup())
    await state.clear()


@dp.message(StateFilter(OrderStates.waiting_for_price), F.document)
async def process_price_file(message: Message, state: FSMContext):
    """Обработка загрузки прайс-листа"""
    user_id = message.from_user.id
    data = get_user_data(user_id)
    
    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте файл Excel")
        return
    
    # Проверяем расширение файла
    file_name = message.document.file_name or ""
    if not file_name.lower().endswith('.xlsx'):
        await message.answer("❌ Пожалуйста, отправьте файл Excel в формате .xlsx")
        return
    
    try:
        file = await bot.get_file(message.document.file_id)
        tmp_path = UPLOAD_DIR / f"{user_id}_price_{file.file_id}.xlsx"
        await bot.download_file(file.file_path, tmp_path)
        data['price_file'] = str(tmp_path)
        
        await message.answer("✅ Прайс-лист загружен!\n\n📤 Теперь загрузите файл 'Заказ на склад' (Excel файл):")
        await state.set_state(OrderStates.waiting_for_warehouse)
    except Exception as e:
        logger.error(f"Ошибка при загрузке прайс-листа: {e}")
        await message.answer(f"❌ Ошибка при загрузке файла: {str(e)}")


@dp.message(StateFilter(OrderStates.waiting_for_warehouse), F.document)
async def process_warehouse_file(message: Message, state: FSMContext):
    """Обработка загрузки заказа на склад"""
    user_id = message.from_user.id
    data = get_user_data(user_id)
    
    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте файл Excel")
        return
    
    # Проверяем расширение файла
    file_name = message.document.file_name or ""
    if not file_name.lower().endswith('.xlsx'):
        await message.answer("❌ Пожалуйста, отправьте файл Excel в формате .xlsx")
        return
    
    try:
        file = await bot.get_file(message.document.file_id)
        tmp_path = UPLOAD_DIR / f"{user_id}_warehouse_{file.file_id}.xlsx"
        await bot.download_file(file.file_path, tmp_path)
        data['warehouse_file'] = str(tmp_path)
        
        await message.answer("✅ Заказ на склад загружен!\n\n📤 Теперь загрузите файл 'Предзаказы клиентов' (Excel файл):")
        await state.set_state(OrderStates.waiting_for_preorders)
    except Exception as e:
        logger.error(f"Ошибка при загрузке заказа на склад: {e}")
        await message.answer(f"❌ Ошибка при загрузке файла: {str(e)}")


@dp.message(StateFilter(OrderStates.waiting_for_preorders), F.document)
async def process_preorders_file(message: Message, state: FSMContext):
    """Обработка загрузки предзаказов и генерация заказа"""
    user_id = message.from_user.id
    data = get_user_data(user_id)
    
    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте файл Excel")
        return
    
    # Проверяем расширение файла
    file_name = message.document.file_name or ""
    if not file_name.lower().endswith('.xlsx'):
        await message.answer("❌ Пожалуйста, отправьте файл Excel в формате .xlsx")
        return
    
    try:
        file = await bot.get_file(message.document.file_id)
        tmp_path = UPLOAD_DIR / f"{user_id}_preorders_{file.file_id}.xlsx"
        await bot.download_file(file.file_path, tmp_path)
        data['preorders_file'] = str(tmp_path)
    except Exception as e:
        logger.error(f"Ошибка при загрузке предзаказов: {e}")
        await message.answer(f"❌ Ошибка при загрузке файла: {str(e)}")
        return
    
    await message.answer("⏳ Обрабатываю файлы и генерирую заказ...")
    
    try:
        # Генерируем заказ (берём свежую конфигурацию поставщика)
        supplier_name = data['supplier']
        config = config_manager.get_supplier_config(supplier_name)
        price_config = config['price_list']
        warehouse_config = config['warehouse_order']
        preorders_config = config['preorders']
        
        generator = OrderGenerator(price_config)
        # Выходной файл всегда в .xlsx
        output_file = OUTPUT_DIR / f"{user_id}_order_{file.file_id}.xlsx"
        
        quantities = generator.generate_order(
            price_file=data['price_file'],
            warehouse_file=data['warehouse_file'],
            preorders_file=data['preorders_file'],
            output_file=str(output_file),
            warehouse_config=warehouse_config,
            preorders_config=preorders_config,
            price_template=config.get('price_template')
        )
        # Если ничего не найдено по складу — отправим предпросмотр для диагностики
        if quantities and sum(quantities.values()) == 0:
            # ничего не зашло во вход (защита от деления на 0 ниже)
            pass
        warehouse_diag = getattr(generator, 'last_diagnostics', {}).get('warehouse') or {}
        if not quantities or len(quantities) == 0 or warehouse_diag.get('total_items_found', 0) == 0:
            try:
                # предпросмотр только первых 10 строк первого листа
                # Файл 'на склад' повторяет структуру прайса -> используем разметку прайса
                article_col = price_config.get('article_col', 0)
                quantity_col = price_config.get('quantity_col', 9)
                preview = generator.preview_warehouse(data['warehouse_file'], article_col, quantity_col, rows=10)
                # краткая сводка
                if warehouse_diag:
                    summary = (
                        f"Строк просмотрено: {warehouse_diag.get('rows_seen', '?')}, "
                        f"артикулов: {warehouse_diag.get('articles_seen', '?')}, "
                        f"кол-во>0: {warehouse_diag.get('valid_qty_rows', '?')}, "
                        f"итемов: {warehouse_diag.get('total_items_found', 0)}"
                    )
                else:
                    summary = "(нет метрик)"
                await message.answer("🔎 Диагностика файла 'Заказ на склад':\n" + summary + "\n\n" + preview[:3500])
            except Exception as _:
                # молча игнорируем предпросмотр, чтобы не прерывать сценарий
                pass
        
        # Отправляем результат
        result_file = FSInputFile(str(output_file))
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 В главное меню", callback_data="menu_main")
        
        await message.answer(
            f"✅ Заказ успешно сгенерирован!\n\n"
            f"📊 Найдено товаров: {len(quantities)}\n"
            f"📦 Общее количество: {sum(quantities.values())}",
            reply_markup=builder.as_markup()
        )
        await message.answer_document(result_file)
        
        # Очищаем данные пользователя
        user_data[user_id] = {
            'price_file': None,
            'warehouse_file': None,
            'preorders_file': None,
            'supplier': None,
            'config': None
        }
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при генерации заказа: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при генерации заказа: {str(e)}")
        await state.clear()
