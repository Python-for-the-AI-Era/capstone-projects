# Task 4: Save context state
def save_session(context):
    context.storage_state(path="state.json")

# Task 4: Load context state
def get_authenticated_context(browser):
    return browser.new_context(storage_state="state.json")