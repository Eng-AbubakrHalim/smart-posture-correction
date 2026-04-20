# How to Push This Project to GitHub

Follow these steps once. After that, your GitHub profile will have a public repo showcasing your award-winning capstone.

---

## Step 1 — Create the GitHub Repository

1. Go to https://github.com/new (make sure you're logged in as Eng-AbubakrHalim)
2. Repository name: `smart-posture-correction`
3. Description: `🏆 Industry Award Winner — Wearable posture correction system using ESP32-C3, custom KiCad PCB, and real-time computer vision (dlib + solvePnP). UTM EECS 2026.`
4. Set to **Public**
5. **Do NOT** tick "Add a README file" — we already have one
6. Click **Create repository**

---

## Step 2 — Open a Terminal (Command Prompt or PowerShell)

Navigate to the `smart-posture-correction` folder inside your Internship folder:

```powershell
cd "C:\Users\abuba\Desktop\Internship\smart-posture-correction"
```

*(Adjust the path if your Internship folder is in a different location)*

---

## Step 3 — Initialize and Push

Run these commands one by one:

```bash
git init
git add .
git commit -m "Initial release: Smart Posture Correction System - Industry Award Winner EECS 2026"
git branch -M main
git remote add origin https://github.com/Eng-AbubakrHalim/smart-posture-correction.git
git push -u origin main
```

GitHub will ask for your username and a **Personal Access Token** (PAT) — not your password.

### Getting a Personal Access Token (if you don't have one):
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token → tick `repo` scope → Generate
3. Copy the token and paste it when Git asks for your password

---

## Step 4 — Verify

Go to: https://github.com/Eng-AbubakrHalim/smart-posture-correction

You should see the README render with the award badge, architecture diagram, and setup guide.

---

## Optional — Add the KiCad PCB Files

Copy your KiCad project files into the `hardware/` folder before pushing:

```
hardware/
├── README.md                    ← already there
├── Capstone pcb.kicad_pro
├── Capstone pcb.kicad_sch
├── Capstone pcb.kicad_pcb
└── Gerbers/
    └── *.gbr
```

Then:
```bash
git add hardware/
git commit -m "Add KiCad PCB design files and Gerbers"
git push
```

---

## Optional — Add Photos

Create an `images/` folder, drop in your project photos, then:

```bash
git add images/
git commit -m "Add project photos"
git push
```

And update the README.md to reference them:
```markdown
![PCB Top View](images/pcb_top.jpg)
![Award Ceremony](images/award_ceremony.jpg)
```
