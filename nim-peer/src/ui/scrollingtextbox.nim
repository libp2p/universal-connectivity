import unicode
from nimwave as nw import nil

import ./context

type ScrollingTextBox* = ref object of nw.Node
  title*: string
  text*: seq[string]
  width*: int
  height*: int
  startingLine: int
  border*: nw.Border

proc new*(
    T: typedesc[ScrollingTextBox],
    title: string = "",
    width: int = 3,
    height: int = 3,
    text: seq[string] = @[],
): T =
  # width and height cannot be less than 3 (2 for borders + 1 for content)
  let height = max(height, 3)
  let width = max(width, 3)
  # height and width - 2 to account for size of box lines (top and botton)
  ScrollingTextBox(
    title: title,
    width: width - 2,
    height: height - 2,
    text: text,
    startingLine: 0,
    border: nw.Border.Single,
  )

proc resize*(node: ScrollingTextBox, width: int, height: int) =
  let height = max(height, 3)
  let width = max(width, 3)
  node.width = width - 2
  node.height = height - 2

proc formatText(node: ScrollingTextBox): seq[string] =
  result = @[]
  result.add(node.title.alignLeft(node.width))
  # empty line after title
  result.add(" ".alignLeft(node.width))
  for i in node.startingLine ..< max(node.startingLine + node.height - 2, 0):
    if i < node.text.len:
      result.add(node.text[i].alignLeft(node.width))
    else:
      result.add(" ".alignLeft(node.width))

proc scrollUp*(node: ScrollingTextBox, speed: int) =
  node.startingLine = max(node.startingLine - speed, 0)

proc scrollDown*(node: ScrollingTextBox, speed: int) =
  let lastStartingLine = max(0, node.text.len - node.height + 2)
  node.startingLine = min(node.startingLine + speed, lastStartingLine)

proc tail(node: ScrollingTextBox) =
  ## focuses window in lowest frame
  node.startingLine = max(0, node.text.len - node.height + 2)

proc isAnsiEscapeSequence(s: string, idx: int): bool =
  ## Check if the substring starting at `idx` is an ANSI escape sequence
  if idx < 0 or idx + 2 >= s.len: # Need at least 3 characters for "\e["
    return false
  if s[idx] == '\e' and s[idx + 1] == '[': # Must start with "\e["
    var i = idx + 2
    while i < s.len and (s[i] in '0' .. '9' or s[i] == ';' or s[i] == 'm'):
      i.inc
    return s[i - 1] == 'm' # Ends with 'm'
  return false

proc chunkString(s: string, chunkSize: int): seq[string] =
  var result: seq[string] = @[]
  var i = 0

  while i < s.len:
    var endIdx = min(i + chunkSize - 1, s.len - 1)

    # Avoid splitting escape sequences
    while endIdx > i and isAnsiEscapeSequence(s, endIdx):
      dec endIdx

    result.add(s[i .. endIdx])
    i = endIdx + 1

  return result

proc push*(node: ScrollingTextBox, newLine: string) =
  if newLine.len == 0 or node.width <= 0:
    return
  for chunk in chunkString(newLine, node.width):
    node.text.add(chunk)
  node.tail()

proc remove*(node: ScrollingTextBox, lineToRemove: string) =
  let idx = node.text.find(lineToRemove)
  if idx >= 0:
    node.text.delete(idx)
    if idx <= node.startingLine:
      node.scrollUp(1)

method render(node: ScrollingTextBox, ctx: var nw.Context[State]) =
  ctx = nw.slice(ctx, 0, 0, node.width + 2, node.height + 2)
  render(
    nw.Box(
      border: node.border,
      direction: nw.Direction.Vertical,
      children: nw.seq(node.formatText()),
    ),
    ctx,
  )
