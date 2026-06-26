import re
from anki import hooks # backend hooks
from anki.notes import Note
from aqt import gui_hooks # gui hooks
from aqt.qt import QShortcut
from PyQt6.QtGui import QKeySequence


## ++ Wrap -selected text- in the editor with -cloze syntax- (SHORTCUT) ++ ##
def wrap_selection(editor):
    js = """
    (() => {
        const sel = window.getSelection().toString();
        if (!sel) {
            alert("No selection detected");
            return;
        }
        document.execCommand('insertText', false, '{{c:' + sel + '}}');
    })();
    """
    editor.web.eval(js)

def setup_shortcut(editor):
    shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), editor.parentWindow)
    shortcut.activated.connect(lambda: wrap_selection(editor))


gui_hooks.editor_did_init.append(setup_shortcut)



## ++ Rendering the cloze syntax in the editor ++ ## 

# The pattern to find our custom cloze markers in 'fields' 
CLOZEHYBRID_WORD_PATTERN = re.compile(r"\{\{c:(.+?)\}\}")

# Pattern to find our custom clozehybrid tags in the HTML (DEFAULT)
CLOZEHYBRID_TARGET_PATTERN = re.compile(r"<clozehybrid-target>(.*?)</clozehybrid-target>")

# Pattern to find custom clozehybrid-forceShow tags in the HTML (FORCESHOW)
CLOZEHYBRID_FORCESHOW_PATTERN = re.compile(r"<clozehybrid-forceShow>(.*?)</clozehybrid-forceShow>")

def on_field_filter(field_text: str, field_name: str, filter_name: str, context) -> str:
    # If Anki sees {{cloze:FieldName}}, wrap the content so we can identify it later (DEFAULT)
    if filter_name == "clozehybrid":
        return f"<clozehybrid-target>{field_text}</clozehybrid-target>"
    
    # ForceShow option Custom Wrap
    if filter_name == "clozehybridforceshow":
        return f"<clozehybrid-forceShow>{field_text}</clozehybrid-forceShow>"
    
    # If it's a normal {{FieldName}} do nothing
    return field_text

# Register the filter hook
hooks.field_filter.append(on_field_filter)

# CSS to make clozehybrid words bold and blue
CLOZEHYBRID_CSS = """
<style>
    .clozehybrid {
        font-weight: bold;
        color: blue;
    }
    .nightMode .clozehybrid {
        color: lightblue; 
    }
</style>
"""

def on_card_will_show(html: str, card, context: str) -> str:
    # Check if we are looking at the Front (Question) or Back (Answer)
    is_front = "Question" in context

    def process_default_field(match: re.Match) -> str:
        field_content = match.group(1) # group part of re
        
        if is_front:
            # Front side: hide the word
            return CLOZEHYBRID_WORD_PATTERN.sub("<span class='clozehybrid'>[...]</span>", field_content)
        else:
            # Back side: reveal the word
            return CLOZEHYBRID_WORD_PATTERN.sub(r"<span class='clozehybrid'>\1</span>", field_content)
        
    def process_forceshow_field(match: re.Match) -> str:
        field_content = match.group(1) # 'group' part of re
        
        # ForceShow: always reveal the word, regardless of front/back
        return CLOZEHYBRID_WORD_PATTERN.sub(r"\1", field_content)

    # Doing all replacements
    new_html = CLOZEHYBRID_TARGET_PATTERN.sub(process_default_field, html) # matches the target pattern in html and processes it using the process_default_field function (parameter passed to processing function is always a "Match" type object)
    new_html = CLOZEHYBRID_FORCESHOW_PATTERN.sub(process_forceshow_field, new_html)

    if new_html != html:
        # If the HTML changed, it means this is a hybrid card. 
        # Attach CSS
        new_html += CLOZEHYBRID_CSS

    return new_html

gui_hooks.card_will_show.append(on_card_will_show)


## ++ MOBILE SUPPORT VERSION (Usefull only for Language Learning) ++ ##

# First 7 fields are mandatory and fixed order for this to work
# The fields in order are:
# 1. Word in the target language
# 2. Word in the native language
# 3. Sentence in the target language with {{c:...}} around the word
# 4. Sentence in the native language
# 5. Audo file in the target language
# 6. Hidden Sentence field (auto-generated text)
# 7. Shown Sentence field (auto-generated text)

def on_unfocus(changed: bool, note: Note, current_field_idx: int) -> bool: # If we return true from this function, Anki will refresh the UI to reflect the changed to fields
    if note.model()['name'] != "ClozeHybrid Mobile":
        return changed
    
    # At least 7 fields are required
    if len(note.fields) < 7:
        return changed

    # Getting indexes of required fields
    TARGET_IDX = 2  # The field with the {{c:...}} / hidden word
    HIDDEN_IDX = 5  # Hidden Sentence field
    SHOWN_IDX = 6   # Shown Sentence field
    satz_text = note.fields[TARGET_IDX]

    # Generating auto-generated field text
    hidden_text = CLOZEHYBRID_WORD_PATTERN.sub('<span class="clozehybrid">[...]</span>', satz_text)
    shown_text = CLOZEHYBRID_WORD_PATTERN.sub(r'<span class="clozehybrid">\1</span>', satz_text)


    did_update = False
    if note.fields[HIDDEN_IDX] != hidden_text:
        note.fields[HIDDEN_IDX] = hidden_text
        did_update = True
        
    if note.fields[SHOWN_IDX] != shown_text:
        note.fields[SHOWN_IDX] = shown_text
        did_update = True

    if did_update:
        return True
    
    return changed

gui_hooks.editor_did_unfocus_field.append(on_unfocus)