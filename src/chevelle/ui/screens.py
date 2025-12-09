"""
Screens for Chevelle TUI.
"""

from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import Static, Button, Label, ProgressBar, RichLog, Input
from textual.containers import Vertical, Horizontal, Center


class BurningScreen(ModalScreen):
    """
    Modal screen shown during the burning process.
    Displays a retro-style terminal log and progress bar.
    """

    CSS = """
    BurningScreen {
        align: center middle;
    }
    
    #burning_container {
        width: 80%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    #burning_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding: 1;
    }
    
    #burning_log {
        height: 1fr;
        border: solid $primary-darken-2;
        background: #0a0a0a;
        padding: 0 1;
    }
    
    #burning_progress {
        height: 3;
        padding: 1;
    }
    
    #burning_status {
        text-align: center;
        padding: 1;
    }
    
    #burning_buttons {
        height: 3;
        align: center middle;
    }
    
    #cancel_btn {
        margin: 0 2;
    }
    
    #burning_info {
        text-align: center;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, disc_name: str = "CD 1", track_count: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.disc_name = disc_name
        self.track_count = track_count

    def compose(self) -> ComposeResult:
        with Vertical(id="burning_container"):
            yield Static(f"BURNING {self.disc_name.upper()}", id="burning_title")
            yield Static(f"{self.track_count} tracks to burn", id="burning_info")
            yield RichLog(id="burning_log", highlight=True, markup=True)
            yield ProgressBar(id="burning_progress", total=100, show_eta=True)
            yield Static("Waiting to start...", id="burning_status")
            with Horizontal(id="burning_buttons"):
                yield Button("Cancel", id="cancel_btn", variant="error")
                yield Button("Close", id="close_btn", variant="primary", disabled=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss({"cancelled": True})
        elif event.button.id == "close_btn":
            self.dismiss({"completed": True})

    def log_message(self, message: str) -> None:
        """Add a message to the burning log."""
        log = self.query_one("#burning_log", RichLog)
        log.write(message)

    def update_progress(self, value: float, status: str = "") -> None:
        """Update the progress bar and status message."""
        progress = self.query_one("#burning_progress", ProgressBar)
        progress.update(total=100, progress=value)
        
        if status:
            status_widget = self.query_one("#burning_status", Static)
            status_widget.update(status)

    def burn_complete(self, success: bool = True) -> None:
        """Called when burning is finished."""
        self.query_one("#cancel_btn", Button).disabled = True
        self.query_one("#close_btn", Button).disabled = False
        
        status = self.query_one("#burning_status", Static)
        if success:
            status.update("[green]Burn completed successfully![/]")
        else:
            status.update("[red]Burn failed[/]")


class ConversionScreen(ModalScreen):
    """
    Modal screen shown during the conversion process.
    """

    CSS = """
    ConversionScreen {
        align: center middle;
    }
    
    #convert_container {
        width: 70%;
        height: 60%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    #convert_title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1;
    }
    
    #convert_log {
        height: 1fr;
        border: solid $primary-darken-2;
        background: #0a0a0a;
        padding: 0 1;
    }
    
    #convert_progress {
        height: 3;
        padding: 1;
    }
    
    #convert_status {
        text-align: center;
        padding: 1;
    }
    
    #convert_buttons {
        height: 3;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="convert_container"):
            yield Static("CONVERTING", id="convert_title")
            yield RichLog(id="convert_log", highlight=True, markup=True)
            yield ProgressBar(id="convert_progress", total=100, show_eta=True)
            yield Static("Starting conversion...", id="convert_status")
            with Horizontal(id="convert_buttons"):
                yield Button("Cancel", id="cancel_btn", variant="error")
                yield Button("Close", id="close_btn", variant="primary", disabled=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss({"cancelled": True})
        elif event.button.id == "close_btn":
            self.dismiss({"cancelled": False, "completed": True})

    def log_message(self, message: str) -> None:
        log = self.query_one("#convert_log", RichLog)
        log.write(message)

    def update_progress(self, current: int, total: int, status: str = "") -> None:
        progress = self.query_one("#convert_progress", ProgressBar)
        progress.update(total=total, progress=current)
        
        if status:
            status_widget = self.query_one("#convert_status", Static)
            status_widget.update(status)

    def conversion_complete(self) -> None:
        """Called when conversion is finished."""
        self.query_one("#cancel_btn", Button).disabled = True
        self.query_one("#close_btn", Button).disabled = False
        self.query_one("#convert_status", Static).update("Conversion complete!")


class NewFolderScreen(ModalScreen):
    """
    Modal screen for creating a new folder.
    """

    CSS = """
    NewFolderScreen {
        align: center middle;
    }
    
    #newfolder_container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    #newfolder_title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1;
    }
    
    #parent_path {
        color: $text-muted;
        padding: 0 0 1 0;
    }
    
    #folder_input {
        margin: 1 0;
    }
    
    #newfolder_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    
    Button {
        margin: 0 1;
    }
    
    #error_msg {
        color: $error;
        text-align: center;
        height: 1;
    }
    """

    def __init__(self, parent_path: Path, **kwargs):
        super().__init__(**kwargs)
        self.parent_path = parent_path

    def compose(self) -> ComposeResult:
        with Vertical(id="newfolder_container"):
            yield Static("Create New Folder", id="newfolder_title")
            yield Static(f"In: {self.parent_path}", id="parent_path")
            yield Input(placeholder="Folder name", id="folder_input")
            yield Static("", id="error_msg")
            with Horizontal(id="newfolder_buttons"):
                yield Button("Create", id="create_btn", variant="primary")
                yield Button("Cancel", id="cancel_btn", variant="default")

    def on_mount(self) -> None:
        self.query_one("#folder_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "create_btn":
            self._create_folder()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._create_folder()

    def _create_folder(self) -> None:
        folder_name = self.query_one("#folder_input", Input).value.strip()
        error_msg = self.query_one("#error_msg", Static)
        
        if not folder_name:
            error_msg.update("Please enter a folder name")
            return
        
        # Validate folder name
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(c in folder_name for c in invalid_chars):
            error_msg.update("Invalid characters in folder name")
            return
        
        new_path = self.parent_path / folder_name
        
        try:
            new_path.mkdir(parents=True, exist_ok=True)
            self.dismiss(new_path)
        except Exception as e:
            error_msg.update(f"Error: {str(e)}")


class BurnSelectScreen(ModalScreen):
    """
    Modal screen for selecting which disc to burn.
    """

    CSS = """
    BurnSelectScreen {
        align: center middle;
    }
    
    #burnselect_container {
        width: 70;
        height: auto;
        max-height: 80%;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    
    #burnselect_title {
        text-align: center;
        text-style: bold;
        color: $warning;
        padding: 1;
    }
    
    #disc_select_list {
        height: auto;
        max-height: 15;
        padding: 1;
    }
    
    .disc_option {
        padding: 1;
        margin: 0 0 1 0;
        background: $surface-darken-1;
    }
    
    .disc_option:hover {
        background: $primary-darken-1;
    }
    
    #burnselect_info {
        color: $text-muted;
        text-align: center;
        padding: 1;
    }
    
    #burnselect_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    
    Button {
        margin: 0 1;
    }
    """

    def __init__(self, discs: list, dest_path, **kwargs):
        super().__init__(**kwargs)
        self.discs = discs
        self.dest_path = dest_path
        self.selected_disc_id = 1

    def compose(self) -> ComposeResult:
        from textual.widgets import RadioSet, RadioButton
        
        with Vertical(id="burnselect_container"):
            yield Static("SELECT DISC TO BURN", id="burnselect_title")
            yield Static(
                "Choose which disc to burn. Make sure you have converted the files first.",
                id="burnselect_info"
            )
            
            with RadioSet(id="disc_radio"):
                for disc in self.discs:
                    mins = int(disc.total_seconds // 60)
                    secs = int(disc.total_seconds % 60)
                    label = f"CD {disc.id} - {len(disc.tracks)} tracks - {mins:02d}:{secs:02d}"
                    yield RadioButton(label, value=disc.id == 1)
            
            with Horizontal(id="burnselect_buttons"):
                yield Button("Burn", id="burn_btn", variant="warning")
                yield Button("Cancel", id="cancel_btn", variant="default")

    def on_radio_set_changed(self, event) -> None:
        """Track which disc is selected."""
        self.selected_disc_id = event.index + 1

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "burn_btn":
            self.dismiss({
                "disc_id": self.selected_disc_id,
                "disc": self.discs[self.selected_disc_id - 1]
            })


class SettingsScreen(ModalScreen):
    """
    Modal screen for configuring burn settings.
    """

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    
    #settings_container {
        width: 65;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    #settings_title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1;
    }
    
    .setting_row {
        height: 3;
        padding: 0 1;
        align: left middle;
    }
    
    .setting_label {
        width: 15;
        padding-right: 1;
    }
    
    .setting_input {
        width: 1fr;
    }
    
    #settings_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    
    Button {
        margin: 0 1;
    }
    
    Select {
        width: 100%;
    }
    """

    def __init__(self, current_settings: dict = None, **kwargs):
        super().__init__(**kwargs)
        self.current_settings = current_settings or {
            "drive": "/dev/sr0",
            "speed": 4,
            "eject": True
        }

    def compose(self) -> ComposeResult:
        from textual.widgets import Select, Switch
        
        with Vertical(id="settings_container"):
            yield Static("SETTINGS", id="settings_title")
            
            # Drive selection
            with Horizontal(classes="setting_row"):
                yield Static("Drive:", classes="setting_label")
                yield Input(
                    value=self.current_settings.get("drive", "/dev/sr0"),
                    placeholder="/dev/sr0",
                    id="drive_input",
                    classes="setting_input"
                )
            
            # Speed selection
            with Horizontal(classes="setting_row"):
                yield Static("Speed:", classes="setting_label")
                yield Select(
                    [(f"{s}x", s) for s in [1, 2, 4, 8, 12, 16, 24, 32, 48]],
                    value=self.current_settings.get("speed", 4),
                    id="speed_select",
                    classes="setting_input"
                )
            
            # Eject after burn
            with Horizontal(classes="setting_row"):
                yield Static("Eject after:", classes="setting_label")
                yield Switch(
                    value=self.current_settings.get("eject", True),
                    id="eject_switch"
                )
            
            # Mode (read-only info)
            with Horizontal(classes="setting_row"):
                yield Static("Mode:", classes="setting_label")
                yield Static("DAO (Disk At Once)", classes="setting_input")
            
            with Horizontal(id="settings_buttons"):
                yield Button("Save", id="save_btn", variant="primary")
                yield Button("Cancel", id="cancel_btn", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from textual.widgets import Select, Switch
        
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            # Gather values
            drive = self.query_one("#drive_input", Input).value
            speed_select = self.query_one("#speed_select", Select)
            speed = speed_select.value if speed_select.value != Select.BLANK else 4
            eject = self.query_one("#eject_switch", Switch).value
            
            self.dismiss({
                "drive": drive,
                "speed": speed,
                "eject": eject,
                "dao": True
            })
