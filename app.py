#!/usr/bin/env python3
import os
import re

def clean_name(name):
    """Bereinigt Dateinamen für openHAB-IDs (nur A-Z, a-z, 0-9 und _)."""
    # Entferne die Endung .log für die ID-Generierung
    base = os.path.splitext(name)[0]
    cleaned = "".join(c if c.isalnum() or c == '_' else '_' for c in base)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")

def is_rotated_file(filename):
    """
    Prüft, ob eine Datei eine rotierte Log-Datei ist.
    Ignoriert Endungen wie .log.1, .log.2026-07-15, .log.gz, .log.zip, etc.
    """
    fn_lower = filename.lower()
    
    # Standard-Ausschlusskriterien:
    # 1. Endet nicht auf .log (z.B. .gz, .zip, .1)
    if not fn_lower.endswith('.log'):
        return True
        
    # 2. Enthält typische Rotationsmuster im Namen (z.B. "openhab.log.2026-07-15" oder "events-1.log")
    # Sucht nach Mustern wie ".log.x" oder Datumsmustern vor/nach dem .log
    rotation_patterns = [
        r'\.log\.\d+',          # .log.1, .log.2 etc.
        r'\d{4}-\d{2}-\d{2}',   # Datum im Format YYYY-MM-DD
        r'-\d+\.log',           # Endet auf -1.log, -2.log (oft bei log-rotation)
        r'\.bak',               # Backup-Dateien
    ]
    
    for pattern in rotation_patterns:
        if re.search(pattern, fn_lower):
            return True
            
    return False

def scan_log_directory(directory_path):
    """Scannt den Pfad nach aktiven Log-Dateien."""
    if not os.path.exists(directory_path):
        print(f"[-] Fehler: Der Pfad '{directory_path}' existiert nicht.")
        return []
        
    if not os.path.isdir(directory_path):
        print(f"[-] Fehler: '{directory_path}' ist kein Verzeichnis.")
        return []

    found_logs = []
    print(f"[*] Scanne Verzeichnis: {directory_path} ...")
    
    for file in os.listdir(directory_path):
        full_path = os.path.join(directory_path, file)
        if os.path.isfile(full_path):
            if file.lower().endswith('.log'):
                if is_rotated_file(file):
                    print(f"    [Ignoriert] Rotierte/Backup Datei: {file}")
                else:
                    found_logs.append({
                        "filename": file,
                        "fullpath": full_path.replace("\\", "/"), # Einheitliche Slashes für openHAB
                        "id": clean_name(file)
                    })
                    print(f"    [Gefunden]  Aktive Log-Datei: {file}")
                    
    return found_logs

def generate_openhab_files(logs):
    """Generiert die network-like logreader .things, .items und .sitemap Dateien."""
    
    # ------------------ THINGS (.things) ------------------
    th = "// openHAB Log Reader Binding - Generierte Things\n\n"
    for log in logs:
        th += f'Thing logreader:reader:{log["id"]} "Log Reader: {log["filename"]}" [\n'
        th += f'    filePath="{log["fullpath"]}",\n'
        th += f'    refreshRate=1000,\n'
        th += f'    errorPatterns="ERROR+",\n'
        th += f'    warningPatterns="WARN+"\n'
        th += f']\n\n'

    # ------------------ ITEMS (.items) ------------------
    it = "// openHAB Log Reader Binding - Generierte Items\n\n"
    for log in logs:
        it += f'// Log Reader Items für {log["filename"]}\n'
        it += f'DateTime Log_{log["id"]}_LastRead "Letzter Lesezeitpunkt [{%1$tY-%1$tm-%1$td %1$tH:%1$tM:%1$tS}]" <time> {{ channel="logreader:reader:{log["id"]}:lastRead" }}\n'
        it += f'Number Log_{log["id"]}_WarningLines "Warnungen seit letztem Lesen [%d]" <warning> {{ channel="logreader:reader:{log["id"]}:warningLines" }}\n'
        it += f'Number Log_{log["id"]}_ErrorLines "Fehler seit letztem Lesen [%d]" <error> {{ channel="logreader:reader:{log["id"]}:errorLines" }}\n'
        it += f'String Log_{log["id"]}_LastWarning "Letzte Warnung [%s]" <warning> {{ channel="logreader:reader:{log["id"]}:lastWarningLine" }}\n'
        it += f'String Log_{log["id"]}_LastError "Letzter Fehler [%s]" <error> {{ channel="logreader:reader:{log["id"]}:lastErrorLine" }}\n\n'

    # ------------------ SITEMAP (.sitemap) ------------------
    sm = 'sitemap logreader label="Log-Überwachung" {\n'
    sm += '    Frame label="Überblick Log-Dateien" {\n'
    for log in logs:
        sm += f'        Text item=Log_{log["id"]}_LastRead label="{log["filename"]}" icon="text" {{\n'
        sm += f'            Frame label="Statistiken" {{\n'
        sm += f'                Text item=Log_{log["id"]}_LastRead\n'
        sm += f'                Text item=Log_{log["id"]}_WarningLines valuecolor=[>0="orange"]\n'
        sm += f'                Text item=Log_{log["id"]}_ErrorLines valuecolor=[>0="red"]\n'
        sm += f'            }}\n'
        sm += f'            Frame label="Letzte Meldungen" {{\n'
        sm += f'                Text item=Log_{log["id"]}_LastWarning\n'
        sm += f'                Text item=Log_{log["id"]}_LastError\n'
        sm += f'            }}\n'
        sm += f'        }}\n'
    sm += '    }\n'
    sm += '}\n'

    # Dateien lokal schreiben
    with open("logreader.things", "w", encoding="utf-8") as f:
        f.write(th)
    with open("logreader.items", "w", encoding="utf-8") as f:
        f.write(it)
    with open("logreader.sitemap", "w", encoding="utf-8") as f:
        f.write(sm)

def main():
    print("=== openHAB Log Reader Config Generator ===")
    
    # Standard-Logverzeichnis vorschlagen (Beispiel für typische Linux/openHABian Installation)
    default_path = "/var/log/openhab"
    if not os.path.exists(default_path):
        default_path = os.getcwd() # Fallback auf aktuellen Ordner

    user_path = input(f"Gib den Pfad zum Log-Ordner an (Standard: {default_path}): ").strip()
    if not user_path:
        user_path = default_path

    logs = scan_log_directory(user_path)
    
    if logs:
        print(f"\n[✔] Scan beendet. {len(logs)} aktive Log-Dateien identifiziert.")
        print("[*] Generiere openHAB Log Reader Konfigurationsdateien...")
        generate_openhab_files(logs)
        
        print("\n=== DATEIEN ERFOLGREICH ERSTELLT! ===")
        print(f" 💾 {os.path.abspath('logreader.things')}")
        print(f" 💾 {os.path.abspath('logreader.items')}")
        print(f" 💾 {os.path.abspath('logreader.sitemap')}")
        print("\nKopiere diese Dateien in deinen openHAB-Konfigurationsordner.")
    else:
        print("\n[-] Keine aktiven .log Dateien im angegebenen Ordner gefunden, die den Kriterien entsprechen.")

if __name__ == "__main__":
    main()
