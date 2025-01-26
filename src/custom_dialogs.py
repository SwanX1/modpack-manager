
from typing import Any
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer
from prompt_toolkit.data_structures import Point
from prompt_toolkit.eventloop import run_in_executor_with_context
from prompt_toolkit.filters import FilterOrBool
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings, merge_key_bindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import AnyContainer, HSplit
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.styles import BaseStyle
from prompt_toolkit.validation import Validator
from prompt_toolkit.widgets import (
  Box,
  Button,
  CheckboxList,
  Dialog,
  Label,
  ProgressBar,
  RadioList,
  TextArea,
  ValidationToolbar,
)
from functools import partial
from typing import Callable, Generic, Sequence, TypeVar

from prompt_toolkit.application.current import get_app
from prompt_toolkit.auto_suggest import AutoSuggest, DynamicAutoSuggest
from prompt_toolkit.buffer import Buffer, BufferAcceptHandler
from prompt_toolkit.completion import Completer, DynamicCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.filters import (
    Condition,
    FilterOrBool,
    has_focus,
    is_done,
    is_true,
    to_filter,
)
from prompt_toolkit.formatted_text import (
    AnyFormattedText,
    StyleAndTextTuples,
    Template,
    to_formatted_text,
)
from prompt_toolkit.formatted_text.utils import fragment_list_to_text
from prompt_toolkit.history import History
from prompt_toolkit.key_binding.key_bindings import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import (
    AnyContainer,
    ConditionalContainer,
    Container,
    DynamicContainer,
    Float,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.controls import (
    BufferControl,
    FormattedTextControl,
    GetLinePrefixCallable,
)
from prompt_toolkit.layout.dimension import AnyDimension
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.margins import (
    ConditionalMargin,
    NumberedMargin,
    ScrollbarMargin,
)
from prompt_toolkit.layout.processors import (
    AppendAutoSuggestion,
    BeforeInput,
    ConditionalProcessor,
    PasswordProcessor,
    Processor,
)
from prompt_toolkit.lexers import DynamicLexer, Lexer
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.validation import DynamicValidator, Validator

def _return_none() -> None:
  "Button handler that returns None."
  get_app().exit()

class FieldDef:
  def __init__(self, key: str = "", name: str = "", default: str = ""):
    self.key = key
    self.name = name
    self.default = default

def multi_input_dialog(
  title: AnyFormattedText = "",
  text: AnyFormattedText = "",
  ok_text: str = "OK",
  cancel_text: str = "Cancel",
  style: BaseStyle | None = None,
  fields: list[FieldDef] = [],
) -> Application[str]:
  """
  Display a text input box.
  Return the given text, or None when cancelled.
  """

  def accept(buf: Buffer) -> bool:
    get_app().layout.focus(ok_button)
    return True

  def ok_handler() -> None:
    get_app().exit(result={key: textfields[key].text for key in textfields})

  ok_button = Button(text=ok_text, handler=ok_handler)
  cancel_button = Button(text=cancel_text, handler=_return_none)

  textfields = {}

  for field in fields:
    textfields[field.key] = TextArea(
      accept_handler=accept,
      multiline=False,
      focus_on_click=True,
      name=field.name,
      text="" if not field.default else field.default,
    )

  body_for_inputs = []

  for field in fields:
    body_for_inputs.extend([Label(text=f"{field.name}:"), textfields[field.key]])

  dialog = Dialog(
    title=title,
    body=HSplit(
      [
        Label(text=text, dont_extend_height=True),
        *[x for x in body_for_inputs],
        ValidationToolbar(),
      ],
      padding=D(preferred=1, max=1),
    ),
    buttons=[ok_button, cancel_button],
    with_background=True,
  )

  return _create_app(dialog, style)


def scrollable_text_dialog(
    title: AnyFormattedText = "",
    text: AnyFormattedText = "",
    ok_text: str = "Ok",
    cancel_text: str | None = "Cancel",
    scrollable: str = "",
    style: BaseStyle | None = None,
) -> Application[bool | None]:
  def ok_handler() -> None:
    get_app().exit(result=True)

  buttons = [
    Button(text=ok_text, handler=ok_handler),
  ]

  if cancel_text:
    buttons.append(Button(text=cancel_text, handler=_return_none))

  dialog = Dialog(
    title=title,
    body=HSplit(
      [
        Label(text=text, dont_extend_height=True),
        TextArea(text=scrollable, read_only=True, scrollbar=True),
      ],
      padding=1,
    ),
    buttons=buttons,
    with_background=True,
  )

  return _create_app(dialog, style)


def _create_app(dialog: AnyContainer, style: BaseStyle | None) -> Application[Any]:
  bindings = KeyBindings()
  bindings.add("tab")(focus_next)
  bindings.add("s-tab")(focus_previous)

  return Application(
    layout=Layout(dialog),
    key_bindings=merge_key_bindings([load_key_bindings(), bindings]),
    mouse_support=True,
    style=style,
    full_screen=True,
  )