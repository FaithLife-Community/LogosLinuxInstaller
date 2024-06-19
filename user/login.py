def get_user_ids(logos_dir):
    # NOTE: Is it possible to have more than one user logged in?
    user_ids = []
    data_dirs = [d for d in logos_dir.rglob('Data/*')]
    if data_dirs:
        user_id = data_dirs[0].name
        if user_id not in user_ids:
            user_ids.append(user_id)
    return user_ids


def get_first_user_id(logos_dir):
    return get_user_ids(logos_dir)[0]
