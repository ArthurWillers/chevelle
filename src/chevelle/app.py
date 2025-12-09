from pathlib import Path
import asyncio
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Header, 
    Footer, 
    Static, 
    DirectoryTree, 
    DataTable,
    Button,
    Input,
    Label,
    Rule,
)
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.reactive import reactive

from .ui.screens import BurningScreen, SettingsScreen, ConversionScreen, NewFolderScreen, BurnSelectScreen
from .core.splitter import Splitter, Track, Disc
from .core.Converter import Converter, ConversionStatus
from .core.burner import Burner, BurnStatus


class SimpleDirectoryTree(DirectoryTree):
    """DirectoryTree that hides hidden files and folders."""
    
    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter out hidden files and directories."""
        return [path for path in paths if not path.name.startswith(".")]


class ChevelleApp(App):
    """
    Chevelle - TUI CD Audio Burner for Linux.
    """

    TITLE = "Chevelle"
    SUB_TITLE = "CD Burner"

    CSS = """
    Screen {
        background: $surface;
    }
    
    /* Main layout */
    #main_container {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 2fr;
        height: 1fr;
    }
    
    /* Left panel - File browser */
    #browser_panel {
        border: solid $primary;
        height: 100%;
    }
    
    #browser_title {
        dock: top;
        text-align: center;
        text-style: bold;
        background: $primary;
        padding: 0 1;
        height: 1;
    }
    
    #directory_tree {
        height: 1fr;
    }
    
    /* Right panel - Workspace */
    #workspace_panel {
        height: 100%;
        padding: 1;
    }
    
    /* Section titles */
    .section_title {
        text-style: bold;
        color: $text;
        padding: 0;
        margin-bottom: 1;
    }
    
    /* Path display boxes */
    .path_box {
        height: 3;
        margin-bottom: 1;
    }
    
    .path_label {
        color: $text-muted;
        height: 1;
    }
    
    .path_value {
        background: $surface-darken-1;
        padding: 0 1;
        height: 2;
        color: $accent;
    }
    
    /* Mode selector */
    .mode_box {
        height: 2;
        margin-bottom: 1;
    }
    
    .mode_value {
        color: $warning;
        margin-left: 1;
    }
    
    /* Disc preview area */
    #disc_preview {
        height: 1fr;
        border: solid $secondary;
        margin: 1 0;
    }
    
    #disc_preview_title {
        dock: top;
        text-align: center;
        background: $secondary;
        height: 1;
    }
    
    #disc_list {
        height: 1fr;
        padding: 1;
    }
    
    .disc_item {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: $surface-darken-1;
    }
    
    .disc_header {
        text-style: bold;
        color: $primary;
    }
    
    .disc_tracks {
        color: $text-muted;
        padding-left: 2;
    }
    
    .disc_time {
        color: $success;
    }
    
    .disc_time_warning {
        color: $warning;
    }
    
    .disc_time_overflow {
        color: $error;
    }
    
    /* Empty state message */
    .empty_message {
        text-align: center;
        color: $text-muted;
        padding: 2;
    }
    
    /* Action buttons */
    #action_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
        padding: 0 1;
        background: $surface-darken-1;
    }
    
    #action_buttons Button {
        margin: 0 1;
    }
    
    /* Status bar */
    #status_bar {
        dock: bottom;
        height: 1;
        background: $primary-darken-2;
        padding: 0 2;
    }
    
    /* Empty state */
    #empty_state {
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    
    /* Input styling */
    Input {
        margin: 0 0 1 0;
    }
    
    Rule {
        margin: 1 0;
        color: $surface-lighten-1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("s", "set_source", "Source", show=True),
        Binding("d", "set_dest", "Dest", show=True),
        Binding("n", "new_folder", "New Folder", show=True),
        Binding("m", "toggle_split_mode", "Mode", show=True),
        Binding("c", "convert", "Convert", show=True),
        Binding("b", "burn", "Burn", show=True),
        Binding("f", "settings", "Settings", show=True),
    ]

    # Reactive state
    source_path: reactive[Path | None] = reactive(None)
    dest_path: reactive[Path | None] = reactive(None)
    split_mode: reactive[str] = reactive("sequential")  # "sequential" or "fill_gaps"
    
    def __init__(self):
        super().__init__()
        self.splitter = Splitter(capacity_minutes=79.5)
        self.discs: list[Disc] = []
        self.tracks: list[Track] = []
        self.home_path = Path.home()
        self.selecting_for = "source"  # "source" or "dest"
        self.converter: Converter | None = None
        self.conversion_cancelled = False
        self.conversion_screen: ConversionScreen | None = None
        self.burner: Burner | None = None
        self.burn_screen: BurningScreen | None = None
        self.burn_cancelled = False
        
        # Settings
        self.burn_device = "/dev/sr0"
        self.burn_speed = 4
        self.burn_eject = True

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal(id="main_container"):
            # Left panel - Directory browser
            with Vertical(id="browser_panel"):
                yield Static("Browse", id="browser_title")
                yield SimpleDirectoryTree(str(self.home_path), id="directory_tree")
            
            # Right panel - Workspace
            with Vertical(id="workspace_panel"):
                # Source path
                with Vertical(classes="path_box"):
                    yield Label("[S] Source folder:", classes="path_label")
                    yield Static("No folder selected", id="source_display", classes="path_value")
                
                # Destination path
                with Vertical(classes="path_box"):
                    yield Label("[D] Destination folder:", classes="path_label")
                    yield Static("No folder selected", id="dest_display", classes="path_value")
                
                # Split mode selector
                with Horizontal(classes="mode_box"):
                    yield Label("[M] Split mode:", classes="path_label")
                    yield Static("Sequential (preserve order)", id="mode_display", classes="mode_value")
                
                yield Rule()
                
                # Disc preview
                with Vertical(id="disc_preview"):
                    yield Static("Disc Preview", id="disc_preview_title")
                    with ScrollableContainer(id="disc_list"):
                        yield Static("Select a source folder to preview discs", classes="empty_message")
                
                # Action buttons
                with Horizontal(id="action_buttons"):
                    yield Button("Source [S]", id="btn_source", variant="default")
                    yield Button("Dest [D]", id="btn_dest", variant="default")
                    yield Button("New Folder [N]", id="btn_newfolder", variant="default")
                    yield Button("Convert [C]", id="btn_convert", variant="primary", disabled=True)
                    yield Button("Burn [B]", id="btn_burn", variant="warning", disabled=True)
        
        # Status bar
        yield Static("Ready", id="status_bar")
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one("#directory_tree", SimpleDirectoryTree)
        tree.show_root = False
        tree.show_guides = True

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """When a directory is selected, show which action is available."""
        path = Path(event.path)
        status = self.query_one("#status_bar", Static)
        
        if self.selecting_for == "source":
            status.update(f"Press S to set [{path.name}] as source")
        else:
            status.update(f"Press D to set [{path.name}] as destination")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        
        if button_id == "btn_source":
            self.action_set_source()
        elif button_id == "btn_dest":
            self.action_set_dest()
        elif button_id == "btn_newfolder":
            self.action_new_folder()
        elif button_id == "btn_convert":
            self.action_convert()
        elif button_id == "btn_burn":
            self.action_burn()

    def action_set_source(self) -> None:
        """Set the source folder from current selection."""
        tree = self.query_one("#directory_tree", SimpleDirectoryTree)
        
        if tree.cursor_node is None:
            self.notify("Select a folder first", severity="warning")
            return
        
        path = Path(tree.cursor_node.data.path)
        if path.is_file():
            path = path.parent
        
        self.source_path = path
        self._load_source_folder(path)

    def action_set_dest(self) -> None:
        """Set the destination folder from current selection."""
        tree = self.query_one("#directory_tree", SimpleDirectoryTree)
        
        if tree.cursor_node is None:
            self.notify("Select a folder first", severity="warning")
            return
        
        path = Path(tree.cursor_node.data.path)
        if path.is_file():
            path = path.parent
        
        self.dest_path = path
        dest_display = self.query_one("#dest_display", Static)
        dest_display.update(str(path))
        
        self._update_buttons()
        self.notify(f"Destination: {path.name}", title="Destination Set")

    def _load_source_folder(self, path: Path) -> None:
        """Load audio files from source folder and organize into discs."""
        # Update display
        source_display = self.query_one("#source_display", Static)
        source_display.update(str(path))
        
        # Find audio files (MP3 and WAV)
        mp3_files = list(path.glob("*.mp3"))
        wav_files = list(path.glob("*.wav"))
        audio_files = mp3_files + wav_files
        
        if not audio_files:
            self.notify(f"No audio files in {path.name}", severity="warning")
            self._show_empty_preview("No audio files found")
            return
        
        # Determine file type
        file_type = "MP3" if mp3_files else "WAV"
        if mp3_files and wav_files:
            file_type = "Mixed (MP3/WAV)"
        
        # Load tracks
        try:
            self.tracks = self.splitter.load_tracks(audio_files)
            
            if not self.tracks:
                self._show_empty_preview("Could not load audio files")
                return
            
            # Split into discs based on selected mode
            if self.split_mode == "sequential":
                self.discs = self.splitter.split_into_discs(self.tracks)
            else:
                self.discs = self.splitter.split_into_discs_filling_gaps(self.tracks)
            
            # Update preview
            self._update_disc_preview()
            self._update_buttons()
            
            total_time = sum(d.total_seconds for d in self.discs)
            mode_name = "Sequential" if self.split_mode == "sequential" else "Fill Gaps"
            self.notify(
                f"Found {len(self.tracks)} {file_type} files -> {len(self.discs)} disc(s) [{mode_name}]",
                title="Source Loaded"
            )
            
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def _show_empty_preview(self, message: str) -> None:
        """Show empty state message in preview."""
        disc_list = self.query_one("#disc_list", ScrollableContainer)
        disc_list.remove_children()
        disc_list.mount(Static(message, classes="empty_message"))

    def _update_disc_preview(self) -> None:
        """Update the disc preview panel with full track listing."""
        disc_list = self.query_one("#disc_list", ScrollableContainer)
        disc_list.remove_children()
        
        for disc in self.discs:
            # Calculate time info
            total_mins = disc.total_seconds / 60
            time_str = self._format_time(disc.total_seconds)
            
            # Color based on capacity
            if total_mins > 80:
                time_class = "disc_time_overflow"
                time_indicator = "[OVERFLOW]"
            elif total_mins >= 74:
                time_class = "disc_time_warning"
                time_indicator = "[NEAR LIMIT]"
            else:
                time_class = "disc_time"
                time_indicator = ""
            
            # Build complete track list
            track_lines = []
            for i, track in enumerate(disc.tracks, 1):
                track_time = self._format_time(track.duration)
                # Truncate long titles
                title = track.title[:40] if len(track.title) > 40 else track.title
                track_lines.append(f"  {i:2}. {title:<40} {track_time}")
            
            # Create disc widget with all tracks
            header = (
                f"[bold]CD {disc.id}[/] - {len(disc.tracks)} tracks - "
                f"[{time_class}]{time_str} {time_indicator}[/]"
            )
            content = header + "\n" + "\n".join(track_lines)
            
            disc_list.mount(Static(content, classes="disc_item"))

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def _update_buttons(self) -> None:
        """Enable/disable action buttons based on state."""
        has_source = self.source_path is not None and len(self.discs) > 0
        has_dest = self.dest_path is not None
        
        convert_btn = self.query_one("#btn_convert", Button)
        burn_btn = self.query_one("#btn_burn", Button)
        
        convert_btn.disabled = not (has_source and has_dest)
        burn_btn.disabled = not (has_source and has_dest)

    def action_toggle_split_mode(self) -> None:
        """Toggle between sequential and fill gaps split modes."""
        if self.split_mode == "sequential":
            self.split_mode = "fill_gaps"
            mode_text = "Fill Gaps (optimize space)"
        else:
            self.split_mode = "sequential"
            mode_text = "Sequential (preserve order)"
        
        # Update display
        mode_display = self.query_one("#mode_display", Static)
        mode_display.update(mode_text)
        
        # Re-split if we have tracks
        if self.tracks:
            if self.split_mode == "sequential":
                self.discs = self.splitter.split_into_discs(self.tracks)
            else:
                self.discs = self.splitter.split_into_discs_filling_gaps(self.tracks)
            
            self._update_disc_preview()
            self.notify(f"Mode: {mode_text} -> {len(self.discs)} disc(s)", title="Split Mode")

    def action_new_folder(self) -> None:
        """Create a new folder in the currently selected directory."""
        tree = self.query_one("#directory_tree", SimpleDirectoryTree)
        
        if tree.cursor_node is None:
            parent_path = self.home_path
        else:
            parent_path = Path(tree.cursor_node.data.path)
            if parent_path.is_file():
                parent_path = parent_path.parent
        
        def handle_result(new_path: Path | None) -> None:
            if new_path:
                self.dest_path = new_path
                dest_display = self.query_one("#dest_display", Static)
                dest_display.update(str(new_path))
                self._update_buttons()
                tree.reload()
                self.notify(f"Created: {new_path.name}", title="Folder Created")
        
        self.push_screen(NewFolderScreen(parent_path), handle_result)

    def action_convert(self) -> None:
        """Convert audio files to WAV and organize into disc folders."""
        if not self.discs or not self.dest_path:
            self.notify("Set source and destination first", severity="warning")
            return
        
        # Check if FFmpeg is available
        try:
            self.converter = Converter()
        except RuntimeError as e:
            self.notify(str(e), severity="error")
            return
        
        self.conversion_cancelled = False
        
        def handle_result(result) -> None:
            if result and result.get("completed"):
                self.notify(
                    f"Converted {len(self.tracks)} files to {len(self.discs)} disc folders",
                    title="Conversion Complete"
                )
            elif result and result.get("cancelled"):
                self.notify("Conversion cancelled", severity="warning")
        
        # Push the conversion screen first
        self.conversion_screen = ConversionScreen()
        self.push_screen(self.conversion_screen, handle_result)
        
        # Start conversion after screen is shown
        self.set_timer(0.1, self._start_conversion_worker)

    def _start_conversion_worker(self) -> None:
        """Start the conversion in a background thread."""
        # Start in a real thread
        thread = threading.Thread(target=self._run_conversion_thread, daemon=True)
        thread.start()

    def _run_conversion_thread(self) -> None:
        """Background worker for conversion - runs in separate thread."""
        total_tracks = sum(len(d.tracks) for d in self.discs)
        converted = 0
        
        # Calculate disc folder naming
        total_discs = len(self.discs)
        disc_digits = 2 if total_discs < 100 else (3 if total_discs < 1000 else 4)
        
        self.call_from_thread(
            self.conversion_screen.log_message,
            f"Starting conversion of {total_tracks} tracks..."
        )
        self.call_from_thread(
            self.conversion_screen.log_message,
            f"Output: {self.dest_path}"
        )
        self.call_from_thread(self.conversion_screen.log_message, "")
        
        for disc in self.discs:
            if self.conversion_cancelled:
                self.call_from_thread(
                    self.conversion_screen.log_message,
                    "[red]Conversion cancelled[/]"
                )
                return
            
            # Create disc folder
            folder_name = f"CD_{disc.id:0{disc_digits}d}"
            disc_folder = self.dest_path / folder_name
            disc_folder.mkdir(parents=True, exist_ok=True)
            
            self.call_from_thread(
                self.conversion_screen.log_message,
                f"[bold cyan]Creating {folder_name}...[/]"
            )
            
            for i, track in enumerate(disc.tracks, 1):
                if self.conversion_cancelled:
                    self.call_from_thread(
                        self.conversion_screen.log_message,
                        "[red]Conversion cancelled[/]"
                    )
                    return
                
                wav_name = f"{track.title}.wav"
                full_output_path = disc_folder / wav_name
                
                self.call_from_thread(
                    self.conversion_screen.log_message,
                    f"  [{i}/{len(disc.tracks)}] {wav_name}"
                )
                
                # Run ffmpeg
                success = self.converter._run_ffmpeg(track.path, full_output_path)
                
                converted += 1
                
                self.call_from_thread(
                    self.conversion_screen.update_progress,
                    converted,
                    total_tracks,
                    f"Converting: {track.title[:30]}..."
                )
                
                if not success:
                    self.call_from_thread(
                        self.conversion_screen.log_message,
                        f"    [red]Error converting {wav_name}[/]"
                    )
        
        self.call_from_thread(self.conversion_screen.log_message, "")
        self.call_from_thread(
            self.conversion_screen.log_message,
            "[green]All conversions complete![/]"
        )
        self.call_from_thread(self.conversion_screen.conversion_complete)

    def action_burn(self) -> None:
        """Open disc selection and burn."""
        if not self.discs or not self.dest_path:
            self.notify("Set source and destination first", severity="warning")
            return
        
        # Check if wodim is available
        try:
            self.burner = Burner(device=self.burn_device, speed=self.burn_speed)
        except RuntimeError as e:
            self.notify(str(e), severity="error")
            return
        
        def handle_disc_select(result):
            if result:
                self._start_burn(result["disc"])
        
        self.push_screen(BurnSelectScreen(self.discs, self.dest_path), handle_disc_select)

    def _start_burn(self, disc: Disc) -> None:
        """Start burning a disc after selection."""
        # Calculate disc folder path
        total_discs = len(self.discs)
        disc_digits = 2 if total_discs < 100 else (3 if total_discs < 1000 else 4)
        folder_name = f"CD_{disc.id:0{disc_digits}d}"
        disc_folder = self.dest_path / folder_name
        
        # Get WAV files
        wav_files = []
        for track in disc.tracks:
            wav_path = disc_folder / f"{track.title}.wav"
            wav_files.append(wav_path)
        
        # Check if files exist
        missing = [f for f in wav_files if not f.exists()]
        if missing:
            self.notify(
                f"Missing {len(missing)} WAV files. Convert first!",
                severity="error"
            )
            return
        
        self.burn_cancelled = False
        
        def handle_burn_result(result):
            if result and result.get("completed"):
                self.notify("Burn completed successfully!", title="Success")
            elif result and result.get("cancelled"):
                self.burner.cancel()
                self.burn_cancelled = True
                self.notify("Burn cancelled", severity="warning")
        
        # Show burn screen
        self.burn_screen = BurningScreen(
            disc_name=f"CD {disc.id}",
            track_count=len(disc.tracks)
        )
        self.push_screen(self.burn_screen, handle_burn_result)
        
        # Store disc for burning
        self._current_burn_disc = disc
        self._current_burn_wav_files = wav_files
        
        # Start burning after screen is shown
        self.set_timer(0.1, self._start_burn_worker)

    def _start_burn_worker(self) -> None:
        """Start the burn in a background thread."""
        thread = threading.Thread(target=self._run_burn_thread, daemon=True)
        thread.start()

    def _run_burn_thread(self) -> None:
        """Background worker for burning - runs in separate thread."""
        wav_files = self._current_burn_wav_files
        
        self.call_from_thread(
            self.burn_screen.log_message,
            f"Starting burn of {len(wav_files)} tracks..."
        )
        self.call_from_thread(
            self.burn_screen.log_message,
            f"Device: {self.burn_device}, Speed: {self.burn_speed}x"
        )
        self.call_from_thread(self.burn_screen.log_message, "")
        
        success = False
        
        for status in self.burner.burn_disc(wav_files, eject=self.burn_eject):
            if self.burn_cancelled:
                self.call_from_thread(
                    self.burn_screen.log_message,
                    "[red]Burn cancelled[/]"
                )
                return
            
            # Log the message
            if status.message:
                self.call_from_thread(
                    self.burn_screen.log_message,
                    status.message
                )
            
            # Update progress
            if status.phase == "burning":
                self.call_from_thread(
                    self.burn_screen.update_progress,
                    status.progress,
                    f"Track {status.track}/{status.total_tracks}"
                )
            elif status.phase == "fixating":
                self.call_from_thread(
                    self.burn_screen.update_progress,
                    99.0,
                    "Fixating disc..."
                )
            elif status.phase == "complete":
                success = True
                self.call_from_thread(
                    self.burn_screen.update_progress,
                    100.0,
                    "Complete!"
                )
                self.call_from_thread(
                    self.burn_screen.log_message,
                    "[green]Burn completed successfully![/]"
                )
            elif status.phase == "error":
                self.call_from_thread(
                    self.burn_screen.log_message,
                    f"[red]Error: {status.error}[/]"
                )
        
        self.call_from_thread(self.burn_screen.burn_complete, success)

    def action_settings(self) -> None:
        """Open settings."""
        def handle_result(result):
            if result:
                self.burn_device = result.get("drive", "/dev/sr0")
                self.burn_speed = result.get("speed", 4)
                self.burn_eject = result.get("eject", True)
                eject_str = "Yes" if self.burn_eject else "No"
                self.notify(
                    f"Device: {self.burn_device}, Speed: {self.burn_speed}x, Eject: {eject_str}",
                    title="Settings Saved"
                )
        
        current_settings = {
            "drive": self.burn_device,
            "speed": self.burn_speed,
            "eject": self.burn_eject
        }
        self.push_screen(SettingsScreen(current_settings), handle_result)

    def watch_source_path(self, old_value, new_value) -> None:
        """React when source path changes."""
        self.selecting_for = "dest" if new_value else "source"

    def watch_dest_path(self, old_value, new_value) -> None:
        """React when dest path changes."""
        pass


if __name__ == "__main__":
    app = ChevelleApp()
    app.run()