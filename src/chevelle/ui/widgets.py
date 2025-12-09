"""
Custom widgets for Chevelle TUI.
"""

from textual.app import ComposeResult
from textual.widgets import Static, DataTable, ProgressBar, Label, TabbedContent, TabPane
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive


class DiscProgressBar(Static):
    """
    A progress bar that shows disc capacity usage.
    Changes color based on usage:
    - Green: < 74min (safe zone)
    - Yellow: 74min - 79.5min (warning zone)  
    - Red: > 80min (overflow - blocks burning)
    """

    total_seconds = reactive(0.0)
    max_seconds = reactive(79.5 * 60)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bar_width = 40

    def compute_percentage(self) -> float:
        """Calculate the fill percentage."""
        if self.max_seconds == 0:
            return 0.0
        return min((self.total_seconds / self.max_seconds) * 100, 100)

    def get_color_class(self) -> str:
        """Determine color based on time usage."""
        minutes = self.total_seconds / 60
        if minutes > 80:
            return "overflow"  # Red
        elif minutes >= 74:
            return "warning"   # Yellow
        else:
            return "safe"      # Green

    def format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def render(self) -> str:
        """Render the progress bar."""
        percentage = self.compute_percentage()
        filled = int((percentage / 100) * self.bar_width)
        empty = self.bar_width - filled

        color_class = self.get_color_class()
        
        # Color codes for the bar
        if color_class == "overflow":
            bar_char = "█"
            color = "[red]"
        elif color_class == "warning":
            bar_char = "█"
            color = "[yellow]"
        else:
            bar_char = "█"
            color = "[green]"

        bar = f"{color}{bar_char * filled}[/]{' ' * empty}"
        
        time_display = f"{self.format_time(self.total_seconds)} / {self.format_time(self.max_seconds)}"
        
        return f"  [{bar}] {time_display}"

    def watch_total_seconds(self, old_value: float, new_value: float) -> None:
        """React when total_seconds changes."""
        self.refresh()


class TrackList(DataTable):
    """
    A DataTable specialized for displaying audio tracks.
    Shows: Order, Title, Duration
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True

    def on_mount(self) -> None:
        """Set up columns when widget is mounted."""
        self.add_column("#", width=4)
        self.add_column("Title", width=40)
        self.add_column("Duration", width=10)

    def add_track(self, order: int, title: str, duration_seconds: float) -> None:
        """Add a track to the list."""
        mins = int(duration_seconds // 60)
        secs = int(duration_seconds % 60)
        duration_str = f"{mins}:{secs:02d}"
        
        self.add_row(str(order), title, duration_str)

    def clear_tracks(self) -> None:
        """Remove all tracks from the list."""
        self.clear()


class DiscPanel(Static):
    """
    A panel representing a single virtual disc.
    Contains the track list and capacity bar.
    """

    def __init__(self, disc_id: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.disc_id = disc_id

    def compose(self) -> ComposeResult:
        yield TrackList(id=f"tracklist_{self.disc_id}")
        yield DiscProgressBar(id=f"progress_{self.disc_id}")


class DiscTabs(Static):
    """
    Container with tabs for multiple discs.
    Each tab contains a DiscPanel.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.disc_count = 1

    def compose(self) -> ComposeResult:
        with TabbedContent(id="disc_tabs"):
            with TabPane("CD 1", id="tab_1"):
                yield DiscPanel(disc_id=1, id="disc_1")

    def add_disc(self) -> None:
        """Add a new disc tab."""
        self.disc_count += 1
        # Note: Dynamic tab addition would require more complex handling
        # For now, we start with CD 1 and can expand later


class WelcomePanel(Static):
    """
    Welcome panel shown when no tracks are loaded.
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "\n\n"
            "  [bold cyan]Welcome to Chevelle[/]\n\n"
            "  [dim]Audio CD Burning Tool for Linux[/]\n\n"
            "  ─────────────────────────────────────\n\n"
            "  [bold]How to use:[/]\n\n"
            "  • Navigate folders in the [cyan]Library[/] panel on the left\n"
            "  • Press [bold green]A[/] to add a folder to the project\n"
            "  • MP3 files will be organized into 79.5min discs\n"
            "  • Press [bold magenta]B[/] to burn the selected disc\n\n"
            "  ─────────────────────────────────────\n\n"
            "  [dim]Shortcuts: [/][bold]Q[/] Quit  [bold]B[/] Burn  [bold]S[/] Settings\n",
            id="welcome_text"
        )


class StatusFooter(Static):
    """
    Custom footer showing disc statistics.
    """

    total_tracks = reactive(0)
    total_time = reactive(0.0)
    disc_count = reactive(1)

    def render(self) -> str:
        time_str = self.format_time(self.total_time)
        return (
            f" [bold]Tracks:[/] {self.total_tracks} | "
            f"[bold]Total Time:[/] {time_str} | "
            f"[bold]Discs:[/] {self.disc_count}"
        )

    def format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"
