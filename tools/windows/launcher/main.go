package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

const defaultAppURL = "https://web-production-08d73.up.railway.app/najjar-al-samoom-used-imported-cars/login.html"

func main() {
	appURL := strings.TrimSpace(os.Getenv("LQ_APP_URL"))
	if appURL == "" {
		appURL = defaultAppURL
	}

	if err := launchApp(appURL); err != nil {
		messageBox("NAJJAR Trading", fmt.Sprintf("تعذر فتح التطبيق:\n%s\n\nالرابط:\n%s", err.Error(), appURL))
		os.Exit(1)
	}
}

func launchApp(appURL string) error {
	candidates := []struct {
		path string
		args []string
	}{}

	programFiles := os.Getenv("ProgramFiles(x86)")
	if programFiles == "" {
		programFiles = `C:\Program Files (x86)`
	}
	programFiles64 := os.Getenv("ProgramFiles")
	if programFiles64 == "" {
		programFiles64 = `C:\Program Files`
	}
	localAppData := os.Getenv("LOCALAPPDATA")

	edgePaths := []string{
		filepath.Join(programFiles64, `Microsoft\Edge\Application\msedge.exe`),
		filepath.Join(programFiles, `Microsoft\Edge\Application\msedge.exe`),
	}
	for _, p := range edgePaths {
		if fileExists(p) {
			candidates = append(candidates, struct {
				path string
				args []string
			}{p, []string{"--new-window", "--start-maximized", appURL}})
		}
	}

	chromePaths := []string{
		filepath.Join(programFiles64, `Google\Chrome\Application\chrome.exe`),
		filepath.Join(programFiles, `Google\Chrome\Application\chrome.exe`),
		filepath.Join(localAppData, `Google\Chrome\Application\chrome.exe`),
	}
	for _, p := range chromePaths {
		if fileExists(p) {
			candidates = append(candidates, struct {
				path string
				args []string
			}{p, []string{"--new-window", "--start-maximized", appURL}})
		}
	}

	for _, c := range candidates {
		cmd := exec.Command(c.path, c.args...)
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
		if err := cmd.Start(); err == nil {
			return nil
		}
	}

	cmd := exec.Command("cmd", "/C", "start", "", appURL)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	return cmd.Start()
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

func messageBox(title, text string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	proc := user32.NewProc("MessageBoxW")
	titlePtr, _ := syscall.UTF16PtrFromString(title)
	textPtr, _ := syscall.UTF16PtrFromString(text)
	proc.Call(0, uintptr(unsafe.Pointer(textPtr)), uintptr(unsafe.Pointer(titlePtr)), 0)
}
