from event_planner_api.app.core.security import create_access_token
# email главного администратора; срок действия, например, 365 дней (секунды)
token = create_access_token({"sub": "admin@ex.com"}, expires_delta=365*24*60*60)
print(token)
