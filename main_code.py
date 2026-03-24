import sys #this is used so that the code will run on all OS for accessing the right text editor
import threading #Used to stop the wx module from crashing
import subprocess #this is used for opeing notepad (On Windows)
from pathlib import Path #for safety when opening any file; but also allows a funny bug 
import wx #this module is used to produce the GUI

LOG_DIR = "Logs" #directory for log folder
ERRORS_DIRNAME = "Errors" #directory for errors folder
SUMMARY_DIRNAME = "Summary" #directory for summary folder

OUTPUT_FILES = {  #defining a dictionary of filenames for each error type
    "serial": "serial_errors.txt",
    "mac": "mac_errors.txt",
    "network": "network_errors.txt",
    "read": "read_errors.txt",
}

ERROR_PATTERNS = {   #defining a dictionary of strings we use to detect each error type inside a log block
    "serial": "Serial MISMATCH",
    "mac": "MAC MISMATCH",
    "network": "Network Name MISMATCH",
    "read": "Failed to read memory",
}

SEPARATOR = "=" * 60 #separator used to split the log into “blocks”

def ensure_output_dirs(errors_dir, summary_dir):  #defining a function to create output folders if they don't exist
    errors_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

def write_block(file, block): #defining a function to write one log block neatly into an output .txt file
    file.write(SEPARATOR + "\n")
    file.write(block)
    if not block.endswith("\n"):
        file.write("\n")
    file.write(SEPARATOR + "\n\n")

def classify_block(block): #defining a function to decide the kind of block we are dealing with (success/specific error/ignore)
    if "[SUCCESS]" in block:
        return "success"

    for error_type, pattern in ERROR_PATTERNS.items():
        if pattern in block:
            return error_type

    return None

#scan one log file, split it into blocks, classify each block, and record results
def process_log_file(filepath, output_handles, counts):
    with filepath.open("r", encoding="utf-8", errors="replace") as log:
        block = ""

        for line in log:
            #separator line = end of current block
            if line.startswith(SEPARATOR):
                if block.strip(): 
                    error_type = classify_block(block)
                    if error_type:
                        counts[error_type] += 1
                        if error_type != "success":
                            write_block(output_handles[error_type], block)
                block = ""
            else:
                block += line.rstrip() + "\n"

        #catch the last block if the file doesn't end with a separator
        if block.strip():
            error_type = classify_block(block)
            if error_type:
                counts[error_type] += 1
                if error_type != "success":
                    write_block(output_handles[error_type], block)

#generate the summary.txt file with totals and success rate
def write_summary(summary_path, counts):
    total_errors = sum(counts[k] for k in ERROR_PATTERNS.keys())
    total_cases = sum(counts.values())

    with summary_path.open("w", encoding="utf-8") as f:
        f.write("=== VERIFICATION SUMMARY ===\n\n")
        # Using the ":>6" formatting for clean, right-aligned error counts in the summary table
        f.write(f"Serial mismatch errors : {counts['serial']:>6}\n") 
        f.write(f"MAC mismatch errors    : {counts['mac']:>6}\n")
        f.write(f"Network errors         : {counts['network']:>6}\n")
        f.write(f"Read errors            : {counts['read']:>6}\n")
        f.write(f"{'-' * 32}\n")
        f.write(f"Total errors           : {total_errors:>6}\n")
        f.write(f"Total passed cases     : {counts['success']:>6}\n")
        f.write(f"{'-' * 32}\n")
        f.write(f"Total cases analyzed   : {total_cases:>6}\n")

        if total_cases > 0: #calculate success rate
            success_rate = (counts["success"] / total_cases) * 100
            f.write(f"\nSuccess rate           : {success_rate:>6.2f}%\n")

#main function to analyze selected logs and produce outputs
def analyze_selected_logs(selected_logs, errors_dir, summary_dir):
    ensure_output_dirs(errors_dir, summary_dir)

    counts = {key: 0 for key in list(ERROR_PATTERNS.keys()) + ["success"]} #keeping counters for each category + success

    output_paths = {  #deciding where output files will be written
        "serial": errors_dir / OUTPUT_FILES["serial"],
        "mac": errors_dir / OUTPUT_FILES["mac"],
        "network": errors_dir / OUTPUT_FILES["network"],
        "read": errors_dir / OUTPUT_FILES["read"],
        "summary": summary_dir / "summary.txt",
    }

    with (  #open output files once, reuse handles while scanning all selected logs
        output_paths["serial"].open("w", encoding="utf-8") as f_serial,
        output_paths["mac"].open("w", encoding="utf-8") as f_mac,
        output_paths["network"].open("w", encoding="utf-8") as f_network,
        output_paths["read"].open("w", encoding="utf-8") as f_read,
    ):
        output_handles = {
            "serial": f_serial,
            "mac": f_mac,
            "network": f_network,
            "read": f_read,
        }

        for log_file in selected_logs:
            process_log_file(log_file, output_handles, counts)

    #write the summary after all files are processed
    write_summary(output_paths["summary"], counts)

    #console output 
    print("\nLog analysis complete!")
    total_errors = sum(counts[k] for k in ERROR_PATTERNS.keys())
    print(f"  Total errors: {total_errors}")
    print(f"  Successes   : {counts['success']}")
    print(f"  Total cases : {sum(counts.values())}")
    print("\nSee summary.txt for detailed statistics.")

    return output_paths

#open an output text file with the system's default editor (Notepad on Windows, etc.)
def open_text_file(path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if sys.platform.startswith("win"):
        subprocess.Popen(["notepad.exe", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])

#used to delete all .txt files in Errors/ and Summary/ folders once checking is complete
def delete_output_files(errors_dir, summary_dir):
    deleted = 0

    for folder in [errors_dir, summary_dir]:
        if not folder.exists():
            continue
        for txt_file in folder.glob("*.txt"):
            try:
                txt_file.unlink()
                deleted += 1
            except Exception:
                pass

    return deleted

#page-1, pick which log files to scan
class SelectLogsPanel(wx.Panel):
    def __init__(self, parent, on_run_callback):
        super().__init__(parent)
        self.on_run_callback = on_run_callback

        vbox = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Step 1: Select log files to scan")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        vbox.Add(title, 0, wx.ALL, 10)

        self.dir_picker = wx.DirPickerCtrl(self, message="Choose Logs folder")
        vbox.Add(self.dir_picker, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.checklist = wx.CheckListBox(self, choices=[])
        vbox.Add(self.checklist, 1, wx.EXPAND | wx.ALL, 10)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_refresh = wx.Button(self, label="Refresh")
        self.btn_all = wx.Button(self, label="Select All")
        self.btn_none = wx.Button(self, label="Clear")
        self.btn_run = wx.Button(self, label="Run Scan")

        hbox.Add(self.btn_refresh, 0, wx.RIGHT, 8)
        hbox.Add(self.btn_all, 0, wx.RIGHT, 8)
        hbox.Add(self.btn_none, 0, wx.RIGHT, 8)
        hbox.AddStretchSpacer(1)
        hbox.Add(self.btn_run, 0)
        vbox.Add(hbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.status = wx.StaticText(self, label="")
        vbox.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(vbox)

        self.btn_refresh.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.btn_all.Bind(wx.EVT_BUTTON, self.on_select_all)
        self.btn_none.Bind(wx.EVT_BUTTON, self.on_clear)
        self.btn_run.Bind(wx.EVT_BUTTON, self.on_run)

        self._set_default_logs_dir()
        self.refresh_file_list()

    #showing the location of the log files
    def _set_default_logs_dir(self):
        script_dir = Path(__file__).resolve().parent
        candidate = script_dir.parent / LOG_DIR
        self.dir_picker.SetPath(str(candidate if candidate.exists() else script_dir.parent))

    def on_refresh(self, event):
        self.refresh_file_list()

    def refresh_file_list(self):
        logs_dir = Path(self.dir_picker.GetPath())
        files = sorted(logs_dir.glob("*.txt"))

        #wx function call
        self.checklist.SetItems([f.name for f in files])

        self._current_files = files
        self.status.SetLabel(f"Found {len(files)} .txt file(s) in: {logs_dir}")

    def on_select_all(self, event):
        for i in range(self.checklist.GetCount()):
            self.checklist.Check(i, True)

    def on_clear(self, event):
        for i in range(self.checklist.GetCount()):
            self.checklist.Check(i, False)

    def on_run(self, event):
        selected = []
        for i, p in enumerate(getattr(self, "_current_files", [])):
            if self.checklist.IsChecked(i):
                selected.append(p)

        if not selected:
            wx.MessageBox("Please select at least one log file.", "No Selection", wx.OK | wx.ICON_WARNING)
            return

        self.btn_run.Disable()
        self.status.SetLabel("Running scan...")

        #running a scan in the background so that the UI doesn't freeze
        self.on_run_callback(
            selected_logs=selected,
            done_callback=self._on_done,
            error_callback=self._on_error
        )

    def _on_done(self, output_paths):
        self.btn_run.Enable()
        self.status.SetLabel("Scan complete.")
        wx.CallAfter(self.GetParent().GetParent().show_results, output_paths)

    def _on_error(self, message):
        self.btn_run.Enable()
        self.status.SetLabel("Scan failed.")
        wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR)

#page-2, options of opening and/or deleting output files
class ResultsPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        vbox = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Step 2: Open outputs / Delete outputs")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        vbox.Add(title, 0, wx.ALL, 10)

        self.btn_open_summary = wx.Button(self, label="Open Summary")
        self.btn_open_serial = wx.Button(self, label="Open Serial Errors")
        self.btn_open_mac = wx.Button(self, label="Open MAC Errors")
        self.btn_open_network = wx.Button(self, label="Open Network Errors")
        self.btn_open_read = wx.Button(self, label="Open Read Errors")

        grid = wx.GridSizer(rows=3, cols=2, vgap=8, hgap=8)
        for b in [
            self.btn_open_summary,
            self.btn_open_serial,
            self.btn_open_mac,
            self.btn_open_network,
            self.btn_open_read,
        ]:
            grid.Add(b, 0, wx.EXPAND)

        vbox.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        vbox.AddSpacer(10)

        self.btn_delete = wx.Button(self, label="Delete all output files (Errors + Summary)")
        vbox.Add(self.btn_delete, 0, wx.EXPAND | wx.ALL, 10)

        self.status = wx.StaticText(self, label="")
        vbox.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(vbox)

        self.btn_open_summary.Bind(wx.EVT_BUTTON, lambda e: self._open("summary"))
        self.btn_open_serial.Bind(wx.EVT_BUTTON, lambda e: self._open("serial"))
        self.btn_open_mac.Bind(wx.EVT_BUTTON, lambda e: self._open("mac"))
        self.btn_open_network.Bind(wx.EVT_BUTTON, lambda e: self._open("network"))
        self.btn_open_read.Bind(wx.EVT_BUTTON, lambda e: self._open("read"))
        self.btn_delete.Bind(wx.EVT_BUTTON, self._delete_all)

        self.output_paths = {}
        self.errors_dir = None
        self.summary_dir = None

    def set_outputs(self, output_paths, errors_dir, summary_dir):
        self.output_paths = output_paths
        self.errors_dir = errors_dir
        self.summary_dir = summary_dir
        self.status.SetLabel("Ready. Click any button to open the file in Notepad.")

    def _open(self, key):
        try:
            path = self.output_paths.get(key)
            if not path:
                raise FileNotFoundError(f"No output path for '{key}'.")
            open_text_file(path)
        except Exception as e:
            wx.MessageBox(str(e), "Open failed", wx.OK | wx.ICON_ERROR)

    def _delete_all(self, event):
        if not self.errors_dir or not self.summary_dir:
            wx.MessageBox("Output folders not found.", "Error", wx.OK | wx.ICON_ERROR)
            return

        dlg = wx.MessageDialog(
            self,
            "This will delete ALL .txt files in Errors and Summary.\n\nContinue?",
            "Confirm Delete",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        res = dlg.ShowModal()
        dlg.Destroy()

        if res != wx.ID_YES:
            return

        deleted_count = delete_output_files(self.errors_dir, self.summary_dir)
        self.status.SetLabel(f"Deleted {deleted_count} file(s).")

#main app window, holds page-1 and page-2, runs the scan in a background thread
class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Log Analyzer (Fishy)", size=(760, 540))
        self.Centre()

        self.book = wx.Simplebook(self)

        self.panel_select = SelectLogsPanel(self.book, on_run_callback=self.run_scan_async)
        self.panel_results = ResultsPanel(self.book)

        self.book.AddPage(self.panel_select, "Select Logs")
        self.book.AddPage(self.panel_results, "Results")
        self.book.SetSelection(0)

        #project root assumed to be parent folder of this script (Code/)
        script_dir = Path(__file__).resolve().parent
        self.project_root = script_dir.parent

        self.errors_dir = self.project_root / ERRORS_DIRNAME
        self.summary_dir = self.project_root / SUMMARY_DIRNAME

    #run scan without freezing the UI
    def run_scan_async(self, selected_logs, done_callback, error_callback):
        def worker():
            try:
                outputs = analyze_selected_logs(
                    selected_logs=selected_logs,
                    errors_dir=self.errors_dir,
                    summary_dir=self.summary_dir,
                )
                wx.CallAfter(done_callback, outputs)
            except Exception as e:
                wx.CallAfter(error_callback, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def show_results(self, output_paths):
        self.panel_results.set_outputs(output_paths, self.errors_dir, self.summary_dir)
        self.book.SetSelection(1)


class App(wx.App):
    def OnInit(self):
        frame = MainFrame()
        frame.Show(True)
        return True


if __name__ == "__main__":
    app = App(False)
    app.MainLoop()
