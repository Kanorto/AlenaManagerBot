# Полное руководство по REST‑API

Этот документ предназначен для разработчиков, которые интегрируют администраторскую панель или Telegram‑бот с API сервиса планирования мероприятий. Каждая операция описана вместе с обязательными заголовками, схемой тела запроса (если необходимо), параметрами запроса и примерами ответов как для успешных, так и для ошибочных случаев. Все маршруты имеют префикс `/api/v1`.

## Аутентификация

Для всех защищённых операций требуется JWT‑токен в заголовке. Токен выдаётся методом входа (`POST /users/login`). Пример заголовка:

```
Authorization: Bearer <your-jwt-token>
```

Все примеры ниже предполагают наличие этого заголовка, если не указано иначе.  Для
внутреннего использования админ‑панелью и ботом можно использовать служебный
токен, полученный через `/users/login`.  Обычные пользователи (клиенты) не
взаимодействуют с API напрямую.

---

## Пользователи и роли

> **Типы пользователей.** В системе есть три уровня привилегий и происхождения аккаунта:
>
> * **super_admin** — главный администратор, который создаётся первым в системе либо задаётся в конфигурации.  Имеет право управлять ролями, назначать администраторов и полностью контролировать систему.
> * **admin** — администратор, которого назначает super_admin.  Может создавать и редактировать события, управлять пользователями из разных мессенджеров, обрабатывать платежи, тикеты поддержки, отзывы и рассылки.
> * **user** — клиент, который создаётся автоматически при обращении через Telegram‑бот или другую социальную сеть.  Такие записи не требуют email/пароля и имеют поля `social_provider` (например, `telegram`, `vk`, `internal`) и `social_id` — идентификатор пользователя в соответствующей сети.
>
> Сотрудники (super_admin и admin) создаются через API регистрации с указанием `email`, `full_name` и `password`.  Клиенты из бота/соцсетей создаются без пароля, но с параметрами `social_provider` и `social_id`.  Роли хранятся в таблице `roles` и могут быть назначены через `/roles/assign`.

### Регистрация пользователя

Регистрация используется для создания как администраторов, так и клиентов из
мессенджеров. Схема запроса зависит от роли и источника учётной записи.

#### Создание администратора

Для сотрудников (super_admin, admin) требуется адрес электронной почты и
пароль.  Первый зарегистрированный пользователь становится
**super_admin**, все последующие созданы через этот маршрут —
**admin**.  В дальнейшем суперадминистратор может назначать
других администраторов через `/roles/assign`.

```
POST /api/v1/users/
Content-Type: application/json

{
  "email": "admin@example.com",
  "full_name": "Администратор",
  "password": "veryStrongPwd"
}
```

**Успешный ответ:** `201 Created`

```json
{
  "id": 1,
  "email": "admin@example.com",
  "full_name": "Администратор",
  "disabled": false
}
```

#### Создание пользователя из мессенджера

При обращении через Telegram‑бот или другую социальную сеть
панель автоматически вызывает этот же маршрут, но без пароля.  Необходимо
указать идентификатор социальной сети и её название.  Поле
``email`` можно опустить — в таком случае система сгенерирует
уникальный surrogate‑email по схеме ``<provider>:<social_id>``.  Этот
адрес не используется для отправки писем, он нужен только для
внутренней идентификации и обеспечения уникальности в базе.

```
POST /api/v1/users/
Content-Type: application/json

{
  "full_name": "Иван Telegram",
  "social_provider": "telegram",
  "social_id": "987654321"
}
```

**Успешный ответ:** `201 Created`

```json
{
  "id": 5,
  "email": "telegram:987654321",
  "full_name": "Иван Telegram",
  "disabled": false
}
```

#### Ошибки при регистрации

| Код | Условие | Пример ответа |
|----:|---------|---------------|
| 400 | В теле отсутствуют обязательные поля | `{ "detail": "Invalid request" }` |
| 409 | Пользователь с таким email или social_id уже существует | `{ "detail": "User already exists" }` |

> **Примечание:** супер‑администратор создаётся только один раз.  Его
учётная запись определяется первым вызовом `/users/` или заранее
установленными настройками.  Клиенты из мессенджеров получают роль
`user` автоматически.

### Вход в систему

**Запрос:**

```
POST /api/v1/users/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "veryStrongPwd"
}
```

**Успешный ответ:** `200 OK`

```json
{
  "access_token": "<jwt-token>",
  "token_type": "bearer"
}
```

**Ошибки:**

| Код | Условие | Пример |
|----:|---------|-------|
| 401 | Неверный email или пароль | `{ "detail": "Invalid credentials" }` |

### Список пользователей

```
GET /api/v1/users/
Authorization: Bearer <token>
```

**Ответ:** `200 OK`

```json
[
  {
    "id": 1,
    "email": "admin@example.com",
    "full_name": "Администратор",
    "disabled": false
  },
  {
    "id": 5,
    "email": null,
    "full_name": "Иван Telegram",
    "disabled": false
  }
]
```

> Список отображает только базовые поля.  Роль пользователя
  (`super_admin`, `admin` или `user`) определяется через связку с
  таблицей `roles` и возвращается косвенно через токен.

### Обновление пользователя

```
PUT /api/v1/users/2
Authorization: Bearer <token>
Content-Type: application/json

{
  "full_name": "Пётр Петров",
  "disabled": true,
  "role_id": 3
}
```

**Успешный ответ:** `200 OK` — возвращает обновлённый профиль.

```json
{
  "id": 2,
  "email": "user@example.com",
  "full_name": "Пётр Петров",
  "disabled": true
}
```

**Ошибки:** `403 Forbidden` — если обычный пользователь пытается изменить чужой профиль; `404 Not Found` — пользователь не существует.

### Удаление пользователя

```
DELETE /api/v1/users/3
Authorization: Bearer <token>
```

**Ответ:** `204 No Content` — пользователь и связанные с ним записи удалены.

**Ошибки:**

| Код | Описание |
|----:|-----------|
| 400 | Попытка удалить себя или главного администратора |
| 403 | Недостаточно прав (не админ) |
| 404 | Пользователь не найден |

> При удалении пользователя каскадно удаляются его бронирования, платежи,
отзывы, тикеты и сообщения поддержки, записи из листа ожидания.

### Управление ролями

Пример создания роли:

```
POST /api/v1/roles/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "planner",
  "permissions": ["events:create", "events:edit"]
}
```

Ответ: `201 Created` с описанием роли. Аналогично работают запросы `PUT`, `DELETE` и `POST /roles/assign` (назначение роли пользователю).

---

## Мероприятия

### Создание события

```
POST /api/v1/events/
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Йога‑курс",
  "description": "Утренняя йога на свежем воздухе",
  "start_time": "2025-09-01T08:00:00",
  "duration_minutes": 60,
  "max_participants": 20,
  "is_paid": false,
  "price": null
}
```

**Ответ:** `201 Created` — объект события.

```json
{
  "id": 5,
  "title": "Йога‑курс",
  "description": "Утренняя йога на свежем воздухе",
  "start_time": "2025-09-01T08:00:00",
  "duration_minutes": 60,
  "max_participants": 20,
  "is_paid": false
}
```

### Список мероприятий

```
GET /api/v1/events?limit=10&offset=0&sort_by=start_time&order=asc&is_paid=false
```

**Ответ:** массив событий. Если фильтры не заданы, выводятся все.

```json
[
  {
    "id": 5,
    "title": "Йога‑курс",
    "description": "Утренняя йога на свежем воздухе",
    "start_time": "2025-09-01T08:00:00",
    "duration_minutes": 60,
    "max_participants": 20,
    "is_paid": false
  },
  ...
]
```

### Получение одного события

```
GET /api/v1/events/5
```

**Ответ:** `200 OK` — объект события, либо `404 Not Found` если не существует.

### Обновление события

```
PUT /api/v1/events/5
Authorization: Bearer <token>
Content-Type: application/json

{
  "description": "Обновлённое описание",
  "max_participants": 25
}
```

**Ответ:** `200 OK` — новое состояние события.

### Дублирование события

```
POST /api/v1/events/5/duplicate
Authorization: Bearer <token>
Content-Type: application/json

{
  "start_time": "2025-09-15T08:00:00"
}
```

**Ответ:** `201 Created` — новый объект события с теми же параметрами, но новой датой начала.

### Удаление события

```
DELETE /api/v1/events/5
Authorization: Bearer <token>
```

**Ответ:** `204 No Content` — событие и связанные с ним записи (бронирования, лист ожидания, платежи, отзывы) удалены.

**Ошибки:** `404 Not Found` — если события нет; `403 Forbidden` — если запрос от пользователя без соответствующих прав.

### Список участников

```
GET /api/v1/events/5/participants?limit=20&offset=0&sort_by=user_id&order=desc
Authorization: Bearer <token>
```

**Ответ:**

```json
[
  {
    "id": 12,
    "user_id": 4,
    "event_id": 5,
    "group_size": 2,
    "status": "pending",
    "created_at": "2025-08-20T10:00:00",
    "is_paid": false,
    "is_attended": false
  },
  ...
]
```

---

## Бронирования

### Создать бронирование

```
POST /api/v1/events/5/bookings
Authorization: Bearer <token>
Content-Type: application/json

{
  "group_size": 3
}
```

**Ответы:**

| Код | Описание | Пример ответа |
|----:|----------|--------------|
| 201 | Места есть — бронирование создано | `{ "id": 15, "user_id": 4, "event_id": 5, "group_size": 3, "status": "pending", "created_at": "2025-08-25T09:00:00", "is_paid": false, "is_attended": false }` |
| 400 | Мест нет — пользователь отправлен в лист ожидания | `{ "detail": "Event is full. You have been added to the waitlist." }` |
| 404 | Событие не найдено | `{ "detail": "Event 5 does not exist" }` |

### Список бронирований

```
GET /api/v1/events/5/bookings?sort_by=created_at&order=desc&limit=10&offset=0
Authorization: Bearer <token>
```

**Ответ:** массив бронирований с возможностью сортировки и пагинации (пример выше).

### Переключить оплату/посещение

```
POST /api/v1/bookings/15/toggle-payment
Authorization: Bearer <token>
```

**Ответ:** `200 OK` — бронирование c обновлённым флагом `is_paid`. Аналогичный запрос для посещения (`/toggle-attendance`).

### Удалить бронирование

```
DELETE /api/v1/bookings/15
Authorization: Bearer <token>
```

**Ответ:** `204 No Content` — бронирование удалено, а если есть свободные места, первые пользователи из листа ожидания автоматически записываются на событие.

**Ошибки:** `404 Not Found` — бронирование не найдено; `403 Forbidden` — недостаточно прав.

---

## Платежи

### Создать платёж

```
POST /api/v1/payments
Authorization: Bearer <token>
Content-Type: application/json

{
  "event_id": 5,
  "amount": 500,
  "currency": "RUB",
  "provider": "yookassa",
  "description": "Оплата за участие"
}
```

**Ответ:** `201 Created`

```json
{
  "id": 21,
  "amount": 500.0,
  "currency": "RUB",
  "description": "Оплата за участие",
  "created_at": "2025-08-25T12:00:00",
  "event_id": 5,
  "provider": "yookassa",
  "status": "pending",
  "external_id": "2ff3c340-d1...",
  "confirmed_by": null,
  "confirmed_at": null
}
```

Если мероприятие бесплатное и провайдер не указан, `provider = "free"` и `status = "success"`.

### Список платежей

```
GET /api/v1/payments?event_id=5&status=pending&sort_by=amount&order=desc&limit=20
Authorization: Bearer <token>
```

**Ответ:** список платежей, отфильтрованный по событию и статусу. Обычные пользователи видят только свои платежи.

### Подтвердить платёж

```
POST /api/v1/payments/21/confirm
Authorization: Bearer <token>
```

**Ответ:** `200 OK` — платёж помечен как `success`, в полях `confirmed_by` и `confirmed_at` указаны оператор и время подтверждения. Бронирования пользователя по этому событию становятся оплачены (`is_paid = true`).

### Удалить платёж

```
DELETE /api/v1/payments/21
Authorization: Bearer <token>
```

**Ответ:** `204 No Content` — платёж удалён, а связанные бронирования лишаются отметки об оплате.

**Ошибки:** `404 Not Found` — платёж не найден; `403 Forbidden` — только администратор может удалять.

### Вебхук ЮKassa

```
POST /api/v1/payments/yookassa/callback
Content-Type: application/json
X-Idempotency-Key: ...
X-Shop-Id: ...
X-Api-Key: ...

{
  "id": "2ff3c340-d1...",
  "status": "succeeded"
}
```

**Ответ:** `200 OK` — сервис обрабатывает уведомление, находит платёж по `external_id`, обновляет его статус и помечает бронирование как оплаченное.

---

## Поддержка

### Создание тикета

```
POST /api/v1/support/tickets
Authorization: Bearer <token>
Content-Type: application/json

{
  "subject": "Ошибка оплаты",
  "content": "Я оплатил, но статус не обновился",
  "attachments": ["invoice.png"]
}
```

**Ответ:** `201 Created`

```json
{
  "id": 7,
  "user_id": 3,
  "subject": "Ошибка оплаты",
  "status": "open",
  "created_at": "2025-08-25T09:45:00",
  "updated_at": "2025-08-25T09:45:00"
}
```

### Список тикетов

```
GET /api/v1/support/tickets?status=open&limit=10&sort_by=updated_at&order=desc
Authorization: Bearer <token>
```

**Ответ:** список тикетов, доступных текущему пользователю.

### Просмотр тикета

```
GET /api/v1/support/tickets/7
Authorization: Bearer <token>
```

**Ответ:** `200 OK`

```json
{
  "ticket": {
    "id": 7,
    "user_id": 3,
    "subject": "Ошибка оплаты",
    "status": "open",
    "created_at": "2025-08-25T09:45:00",
    "updated_at": "2025-08-25T09:45:00"
  },
  "messages": [
    {
      "id": 11,
      "ticket_id": 7,
      "content": "Я оплатил, но статус не обновился",
      "created_at": "2025-08-25T09:45:00",
      "sender_role": "user",
      "user_id": 3,
      "admin_id": null,
      "attachments": ["invoice.png"]
    },
    ...
  ]
}
```

### Ответ на тикет

```
POST /api/v1/support/tickets/7/reply
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "Мы проверим ваш платёж",
  "attachments": []
}
```

**Ответ:** `201 Created` — сообщение оператора.

### Изменение статуса тикета

```
PUT /api/v1/support/tickets/7/status
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "resolved"
}
```

**Ответ:** `200 OK` — тикет переведён в новый статус.

### Удаление тикета

```
DELETE /api/v1/support/tickets/7
Authorization: Bearer <token>
```

**Ответ:** `204 No Content` — тикет и его сообщения удалены. Только администратор имеет право на эту операцию.

---

## Отзывы

### Оставить отзыв

```
POST /api/v1/reviews
Authorization: Bearer <token>
Content-Type: application/json

{
  "event_id": 5,
  "rating": 4,
  "comment": "Интересное занятие, спасибо!"
}
```

**Ответ:** `201 Created`

```json
{
  "id": 9,
  "event_id": 5,
  "user_id": 3,
  "rating": 4,
  "comment": "Интересное занятие, спасибо!",
  "approved": false,
  "created_at": "2025-08-25T12:30:00",
  "moderated_by": null,
  "moderated_at": null
}
```

**Ошибки:** `400 Bad Request` — если пользователь не посещал событие; `404 Not Found` — если `event_id` не существует.

### Список отзывов

```
GET /api/v1/reviews?event_id=5&approved=true&sort_by=rating&order=desc&limit=5
Authorization: Bearer <token>
```

**Ответ:** массив отзывов, отфильтрованный и отсортированный по указанным параметрам. Обычный пользователь видит только свои отзывы.

### Модерация отзыва

```
POST /api/v1/reviews/9/moderate
Authorization: Bearer <token>
Content-Type: application/json

{
  "approved": true,
  "reason": "Спасибо за ваш отзыв"
}
```

**Ответ:** `200 OK` — отзыв обновлён, поле `approved` изменено.

### Удаление отзыва

```
DELETE /api/v1/reviews/9
Authorization: Bearer <token>
```

**Ответ:** `204 No Content` — отзыв удалён. Удалять может автор или администратор.

---

## Рассылки

### Создать рассылку

```
POST /api/v1/mailings
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Новое мероприятие",
  "content": "Приглашаем вас на уникальное событие...",
  "filters": {
    "event_id": 5,
    "is_paid": true,
    "is_attended": false
  }
}
```

**Ответ:** `201 Created` — объект рассылки.

### Список рассылок

```
GET /api/v1/mailings?limit=20&sort_by=created_at&order=desc
Authorization: Bearer <token>
```

**Ответ:** массив рассылок. Каждая содержит фильтры и данные о последней отправке.

### Отправить рассылку

```
POST /api/v1/mailings/4/send
Authorization: Bearer <token>
```

**Ответ:** `200 OK` — рассылка отправлена, для каждого получателя создаётся запись в `mailing_logs`.

### Удалить рассылку

```
DELETE /api/v1/mailings/4
Authorization: Bearer <token>
```

**Ответ:** `204 No Content` — рассылка и логи удалены.

---

## Шаблоны сообщений и FAQ

### Шаблоны

- **Получить все**: `GET /api/v1/messages/`
- **Получить один**: `GET /api/v1/messages/{key}`
- **Создать/обновить**:

  ```
  POST /api/v1/messages/welcome
  Authorization: Bearer <token>
  Content-Type: application/json

  {
    "content": "Добро пожаловать!",
    "buttons": [
      { "text": "Записаться", "callback": "book" },
      { "text": "Мои записи", "callback": "my_bookings" }
    ]
  }
  ```

  Ответ: `200 OK` — создан или обновлён шаблон.

- **Удалить шаблон**: `DELETE /api/v1/messages/{key}`

### Информационное сообщение

`GET /api/v1/info` возвращает базовый текст (ключ `info`), набор кнопок и сокращённый список FAQ.

### FAQ

```
GET /api/v1/faqs?limit=10&sort_by=position
```

Ответ: массив коротких вопросов. Для получения полного ответа — `GET /api/v1/faqs/{id}`.

Создание, обновление и удаление FAQ выполняются администратором (`POST`, `PUT`, `DELETE /faqs`).

---

## Настройки

- **Список**: `GET /api/v1/settings` — массив объектов `{ "key", "value", "type" }`.
- **Получить**: `GET /api/v1/settings/{key}` — возвращает одно значение.
- **Создать/обновить**:

  ```
  POST /api/v1/settings/yookassa_shop_id
  Authorization: Bearer <token>
  Content-Type: application/json

  {
    "value": "123456",
    "type": "string"
  }
  ```

- **Удалить**: `DELETE /api/v1/settings/{key}`

Настройки позволяют конфигурировать систему без перезапуска (например, менять текст сообщений, лимиты, ключи платёжных систем).

---

## Статистика

### Общая статистика

```
GET /api/v1/statistics/overview
Authorization: Bearer <token>
```

**Ответ:**

```json
{
  "users_count": 12,
  "events_count": 5,
  "bookings_count": 23,
  "payments_count": 18,
  "reviews_count": 9,
  "support_tickets_total": 3,
  "support_tickets_open": 1,
  "waitlist_count": 4,
  "total_revenue": 17500.0
}
```

### Статистика по мероприятиям

```
GET /api/v1/statistics/events?sort_by=revenue&order=desc&limit=5
Authorization: Bearer <token>
```

**Ответ:** массив, каждый элемент содержит базовые данные события и следующие метрики:

```json
[
  {
    "id": 5,
    "title": "Йога‑курс",
    "start_time": "2025-09-01T08:00:00",
    "price": 0.0,
    "max_participants": 20,
    "total_bookings": 10,
    "paid_bookings": 6,
    "attended_bookings": 5,
    "waitlist_count": 2,
    "available_seats": 10,
    "revenue": 3000.0
  }
]
```

Параметры `sort_by` принимают значения: `id`, `title`, `start_time`,
`total_bookings`, `paid_bookings`, `attended_bookings`, `waitlist_count`,
`available_seats`, `revenue`.  Параметр `order` может быть `asc` или
`desc`.  Параметры `limit` и `offset` управляют пагинацией.

---

## Аудит и логирование

Модуль аудита фиксирует каждую значимую операцию (создание, обновление, удаление)
над основными сущностями: пользователями, событиями, бронированиями, платежами,
тикетами поддержки, отзывами, рассылками, шаблонами сообщений, FAQ и настройками.
Записи хранятся в таблице `audit_logs` с полями:

- `id` — идентификатор записи;
- `user_id` — кто выполнил операцию (может быть `null` для системных процессов);
- `action` — тип действия (`create`, `update`, `delete`);
- `object_type` — тип объекта (например, `event`, `booking`, `payment`);
- `object_id` — идентификатор объекта (если применимо);
- `timestamp` — время события;
- `details` — дополнительные данные (в формате JSON).

### Получить журнал аудита

```
GET /api/v1/audit/logs
Authorization: Bearer <admin-token>
```

**Query‑параметры:**

| Параметр   | Тип    | Описание                                                 |
|------------|--------|----------------------------------------------------------|
| `user_id`  | int    | Фильтр по ID пользователя‑инициатора                    |
| `object_type` | str | Тип объекта (`event`, `booking`, `payment`, `user` …)    |
| `action`   | str    | Действие (`create`, `update`, `delete`)                 |
| `start_date` | str (YYYY-MM-DD) | Начальная дата по полю `timestamp`           |
| `end_date` | str (YYYY-MM-DD) | Конечная дата по полю `timestamp`             |
| `limit`    | int    | Количество записей (по умолчанию 100, максимум 500)     |
| `offset`   | int    | Смещение для пагинации                                   |

**Пример запроса:**

```
GET /api/v1/audit/logs?object_type=event&action=create&limit=10
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Успешный ответ:** `200 OK`

```json
[
  {
    "id": 42,
    "user_id": 1,
    "action": "create",
    "object_type": "event",
    "object_id": 12,
    "timestamp": "2025-08-27T14:03:00",
    "details": {"title": "Йога"}
  },
  ...
]
```

**Ошибки:**

| Код | Условие |
|----:|---------|
| 403 | Запрос от пользователя без прав администратора |

---

## Заключение

Данный документ охватывает каждый маршрут API с примером запроса, заголовков и возможных ответов. Если в процессе работы вы обнаружите несоответствия между документацией и фактическим поведением сервиса, это повод улучшить реализацию и обновить данный документ.