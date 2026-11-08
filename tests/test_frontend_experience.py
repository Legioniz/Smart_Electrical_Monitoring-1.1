from scripts.verify_frontend_experience import verify


def test_brief_v11_frontend_experience_contract():
    errors = verify()
    assert not errors, "Frontend experience verification failed:\n" + "\n".join(errors)
