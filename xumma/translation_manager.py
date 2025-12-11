import os
import polib


class TranslationManager:
    """
    A class to manage translations using .po files.
    """

    def __init__(self, translations_path="translations"):
        self.translations_path = translations_path
        self.translations = {}
        self._load_translations()

    def _load_translations(self):
        """
        Load all .po files from the translations directory into memory.
        """
        if not os.path.exists(self.translations_path):
            raise FileNotFoundError(
                f"Translations directory '{self.translations_path}' not found.")

        for lang_file in os.listdir(self.translations_path):
            if lang_file.endswith(".po"):
                lang_code = os.path.splitext(lang_file)[0]
                po = polib.pofile(os.path.join(
                    self.translations_path, lang_file))
                # Store translations as a dictionary: {msgid: msgstr}
                self.translations[lang_code] = {
                    entry.msgid: entry.msgstr for entry in po}

    def translate(self, lang_code, msgid):
        """
        Get the translation for a given msgid in the specified language.

        :param lang_code: Language code (e.g., "en", "ro", "ru")
        :param msgid: The original message ID
        :return: The translated string or the original msgid if not found
        """
        return self.translations.get(lang_code, {}).get(msgid, msgid)  # Fallback to msgid if no translation exists

    def add_translation(self, lang_code, msgid, msgstr):
        """
        Add or update a translation entry in the .po file for a specific language.

        :param lang_code: Language code (e.g., "en", "ro", "ru")
        :param msgid: The original message ID
        :param msgstr: The translation string
        """
        po_file_path = os.path.join(self.translations_path, f"{lang_code}.po")

        if not os.path.exists(po_file_path):
            # Create a new PO file if it doesn't exist
            po = polib.POFile()
        else:
            po = polib.pofile(po_file_path)

        # Check if the entry already exists
        entry = po.find(msgid)
        if entry:
            entry.msgstr = msgstr  # Update translation
        else:
            # Add new translation
            po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))

        po.save(po_file_path)  # Save changes to the file
        self._load_translations()  # Reload translations into memory
