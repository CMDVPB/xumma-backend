ROLE_ADMIN = "level_admin"
ROLE_MANAGER = "level_manager"
ROLE_DRIVER = "level_driver"
ROLE_DISPATCHER = "level_dispatcher"
ROLE_ACCOUNTANT = "level_accountant"

ALL_ROLES = {
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_DRIVER,
    ROLE_DISPATCHER,
    ROLE_ACCOUNTANT,
}


def get_user_roles(user):
    return set(user.groups.values_list("name", flat=True))
