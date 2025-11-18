from UI import console_handler as ch

def ws_info(message, details=None):
    ch.ws_info("WS_SERVER", message, details)

def ws_success(message, details=None):
    ch.ws_success("WS_SERVER", message, details)

def ws_warning(message, details=None):
    ch.ws_warning("WS_SERVER", message, details)

def ws_error(message, details=None, suggestions=None):
    ch.ws_error("WS_SERVER", message, details, suggestions)
