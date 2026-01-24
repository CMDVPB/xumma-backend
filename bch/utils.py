async def get_user_company_async(user):
    """
    Async function to get the company associated with the user.
    """
    # print('UT759', user)

    if user.is_anonymous:
        return None

    return await user.company_set.all().afirst()
