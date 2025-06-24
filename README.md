# Laser-Cutting Microscope GUI – README

This repository contains the Python-based software used to operate a **custom-built laser-cutting microscope** designed for the high-precision ablation of graphene. Developed as part of a bachelor thesis at LMU Munich, the system integrates optical imaging, motor control, and laser micromachining in a unified **Graphical User Interface (GUI)** built with PyQt5.

---

## 🧠 Project Purpose

The GUI controls a microscope platform capable of performing laser ablation on exfoliated graphene flakes. 

For technical and theoretical background, see the associated [Bachelor Thesis](#) (June 2025, Carlos Steiner Navarro).

---

## 🖥️ Main Components

### GUI (`gui.py`)
- Main application entry point
- Controls camera view, laser, motors
- Integrates modules: `CameraView.py`, `ESP301.py`, `NPILaser.py`, and UI helpers

### Camera & Drawing (`CameraView.py`)
- Live camera feed via `amcam.py`
- Mouse-based drawing of lines, rectangles, quadrilaterals, and filled shapes
- Conversion from pixel to motor coordinates (calibration required)

### Motor Control (`ESP301.py`)
- Serial control of Newport ESP301 stepper motors (XYZ axes)
- Backlash correction, joystick movement, speed/acceleration settings

### Laser Control (`NPILaser.py`)
- Serial communication with NPI laser system
- Laser on/off switching and safety prompts

### GUI Utilities (`GuiHelper.py`, `ClickableCameraLabel.py`)
- Widget layouts, buttons, and graphical interaction logic

---

## 🔧 Requirements

- Python ≥ 3.6  
- PyQt5  
- NumPy, Matplotlib, SciPy  
- Serial communication support (`pyserial`)  
- `amcam.py` library (for camera control)

---

## 🛠️ Hardware Used

- Olympus 50x NIR objective (0.65 NA)
- Mitutoyo VMU-V microscope base
- NPI 1064 nm picosecond pulsed laser
- ESP301 Newport motion controller (3 axes)
- AmScope camera

---

## 🚀 Getting Started

```bash
# Launch GUI
python gui.py
```

- Use joystick mode to find your flake  
- Draw shapes directly on the live camera image  
- Click “Perform” to begin cutting (ensure laser safety protocols!)  

---

## 📊 Experimental Use

This software was used to extract:
- Layer-dependent ablation thresholds (see: `Appendix A.0.3`)
- Time-incubation fluence models
- Scan-speed dependent cut widths

All scripts used for data analysis (e.g., fitting 1/N scaling laws) are provided in the appendix section of the thesis.

---

## 📎 Notes

- GUI assumes calibration: 1 px ≈ 8.9e-5 mm  
- Focus must be manually adjusted before cutting (NIR ≠ visible)  
- Cutting quality is highly dependent on speed, focus, and layer number  
- ⚠️ **Always wear laser safety goggles when operating the system**  

---

## 🧪 Citation

**Carlos Steiner Navarro**, “Development of a Laser-Cutting Microscope and Analysis of Graphene Ablation Process”, Ludwig-Maximilians-Universität München, 2025.
