import ssl


_original_create_default_context = ssl.create_default_context


def _create_default_context_without_strict(*args, **kwargs):
    context = _original_create_default_context(*args, **kwargs)
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


ssl.create_default_context = _create_default_context_without_strict
ssl._create_default_https_context = _create_default_context_without_strict
