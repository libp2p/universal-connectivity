package main

import (
	"fmt"
	"io"
	"time"

	"github.com/gdamore/tcell/v2"
	"github.com/rivo/tview"
)

// ChatUI is a Text User Interface (TUI) for a ChatRoom.
// The Run method will draw the UI to the terminal in "fullscreen"
// mode. You can quit with Ctrl-C, or by typing "/quit" into the
// chat prompt.
type ChatUI struct {
	cr        *ChatRoom
	app       *tview.Application
	peersList *tview.TextView
	msgBox    *tview.TextView
	sysBox    *tview.TextView

	msgW         io.Writer
	sysW         io.Writer
	inputCh      chan string
	doneCh       chan struct{}
	uiUpdateChan chan func()
}

// NewChatUI returns a new ChatUI struct that controls the text UI.
// It won't actually do anything until you call Run().
func NewChatUI(cr *ChatRoom) *ChatUI {
	app := tview.NewApplication()

	// make a text view to contain our chat messages
	msgBox := tview.NewTextView()
	msgBox.SetDynamicColors(true)
	msgBox.SetBorder(true)
	msgBox.SetTitle(fmt.Sprintf("Room: %s", cr.roomName))
	msgBox.SetScrollable(true)

	// make a text view to contain our error messages
	sysBox := tview.NewTextView()
	sysBox.SetDynamicColors(true)
	sysBox.SetBorder(true)
	sysBox.SetTitle("System")
	sysBox.SetScrollable(true)

	// an input field for typing messages into
	inputCh := make(chan string, 32)
	input := tview.NewInputField().
		SetLabel(cr.nick + " > ").
		SetFieldWidth(0).
		SetFieldBackgroundColor(tcell.ColorBlack)

	// the done func is called when the user hits enter, or tabs out of the field
	input.SetDoneFunc(func(key tcell.Key) {
		if key != tcell.KeyEnter {
			// we don't want to do anything if they just tabbed away
			return
		}
		line := input.GetText()
		if line == "" {
			// ignore blank lines
			return
		}

		// bail if requested
		if line == "/quit" {
			app.Stop()
			return
		}

		// send the line onto the input chan and reset the field text
		inputCh <- line
		input.SetText("")
	})

	// make a text view to hold the list of peers in the room, updated by ui.refreshPeers()
	peersList := tview.NewTextView()
	peersList.SetBorder(true)
	peersList.SetTitle("Peers")

	// chatPanel is a horizontal box with messages on the left and peers on the right
	// the peers list takes 20 columns, and the messages take the remaining space
	chatPanel := tview.NewFlex().
		AddItem(msgBox, 0, 1, false).
		AddItem(peersList, 20, 1, false)

	// flex is a vertical box with the chatPanel on top and the input field at the bottom.
	flex := tview.NewFlex().
		SetDirection(tview.FlexRow).
		AddItem(chatPanel, 0, 3, false).
		AddItem(sysBox, 0, 2, false).
		AddItem(input, 2, 1, true)

	app.SetRoot(flex, true)

	return &ChatUI{
		cr:           cr,
		app:          app,
		peersList:    peersList,
		msgBox:       msgBox,
		sysBox:       sysBox,
		msgW:         msgBox,
		sysW:         sysBox,
		inputCh:      inputCh,
		doneCh:       make(chan struct{}, 1),
		uiUpdateChan: make(chan func(), 256),
	}
}

func (ui *ChatUI) uiUpdater() {
	for f := range ui.uiUpdateChan {
		ui.app.QueueUpdateDraw(f)
	}
}

// Run starts the chat event loop in the background, then starts
// the event loop for the text UI.
func (ui *ChatUI) Run() error {
	go ui.handleEvents()
	go ui.uiUpdater()
	defer ui.end()

	return ui.app.Run()
}

// end signals the event loop to exit gracefully
func (ui *ChatUI) end() {
	close(ui.uiUpdateChan)
	ui.doneCh <- struct{}{}
}

// refreshPeers pulls the list of peers currently in the chat room and
// displays the last 8 chars of their peer id in the Peers panel in the ui.
func (ui *ChatUI) refreshPeers() {
	peers := ui.cr.ListPeers()

	// clear is thread-safe
	ui.peersList.Clear()

	for _, p := range peers {
		fmt.Fprintln(ui.peersList, shortID(p))
	}
}

// displayChatMessage writes a ChatMessage from the room to the message window,
// with the sender's nick highlighted in green.
func (ui *ChatUI) displayChatMessage(cm *ChatMessage) {
	prompt := withColor("green", fmt.Sprintf("<%s>:", cm.SenderNick))
	fmt.Fprintf(ui.msgW, "%s %s\n", prompt, cm.Message)
	ui.msgBox.ScrollToEnd()
}

// displayChatMessage writes a ChatMessage from the room to the message window,
// with the sender's nick highlighted in green.
func (ui *ChatUI) displaySysMessage(cm *ChatMessage) {
	fmt.Fprintf(ui.sysW, "%s\n", cm.Message)
	logger.Info(cm.Message)
	ui.sysBox.ScrollToEnd()
}

// displaySelfMessage writes a message from ourself to the message window,
// with our nick highlighted in yellow.
func (ui *ChatUI) displaySelfMessage(msg string) {
	prompt := withColor("yellow", fmt.Sprintf("<%s>:", ui.cr.nick))
	fmt.Fprintf(ui.msgW, "%s %s\n", prompt, msg)
	ui.msgBox.ScrollToEnd()
}

// handleEvents runs an event loop that sends user input to the chat room
// and displays messages received from the chat room. It also periodically
// refreshes the list of peers in the UI.
func (ui *ChatUI) handleEvents() {
	peerRefreshTicker := time.NewTicker(time.Second)
	defer peerRefreshTicker.Stop()

	for {
		select {
		case input := <-ui.inputCh:
			// when the user types in a line, publish it to the chat room and print to the message window
			err := ui.cr.Publish(input)
			if err != nil {
				printErr("publish error: %s", err)
			}

			ui.app.QueueUpdateDraw(func() {
				if err != nil {
					fmt.Fprintf(ui.sysW, "[red]publish error: %s[-]\n", err)
				}
				ui.displaySelfMessage(input)
			})

		case m := <-ui.cr.Messages:
			// when we receive a message from the chat room, print it to the message window
			ui.app.QueueUpdateDraw(func() {
				ui.displayChatMessage(m)
			})

		case s := <-ui.cr.SysMessages:
			// when we receive a system message, print it to the system window
			ui.app.QueueUpdateDraw(func() {
				ui.displaySysMessage(s)
			})

		case <-peerRefreshTicker.C:
			// refresh the list of peers in the chat room periodically
			ui.app.QueueUpdateDraw(func() {
				ui.refreshPeers()
			})

		case <-ui.cr.ctx.Done():
			return

		case <-ui.doneCh:
			return
		}
	}
}

// withColor wraps a string with color tags for display in the messages text box.
func withColor(color, msg string) string {
	return fmt.Sprintf("[%s]%s[-]", color, msg)
}
