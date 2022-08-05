from import_export import widgets


class BooleanWidgetValidated(widgets.BooleanWidget):
    # Raise an error when no suitable value found.
    # The stock boolean widget doesn't do this!
    # Also support 'checked' for True
    def render(self, value, obj=None):
        if value is None:
            return ""
        return 'TRUE' if value else 'FALSE'

    def clean(self, value, row=None, *args, **kwargs):
        value = value.lower()
        if value in ["", None, "null", "none"]:
            return None
        elif value in ["1", 1, True, "true", 'checked']:
            return True
        elif value in ["0", 0, False, "false"]:
            return False
        else:
            raise ValueError("Enter a valid boolean value.")

    def get_help_html(self):
        return """Valid boolean values
        True: <code>"1", 1, "TRUE", 'checked'</code>;
        False: <code>"0", 0, "FALSE"</code>;
        Null: <code>"" (empty string), "NULL", "none"</code>.
        """
