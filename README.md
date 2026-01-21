# pixi-IsaacLab-unitreeG1

Two Pixi environments are provided:
- `unitree-rl-lab` for **IsaacLab / Isaac Sim** and **Unitree RL Lab (G1)** workflows.
- `unitree-mujoco` for **Unitree MuJoCo** (C++/Python simulator) workflows.

This repository tracks the **environment definition** (Pixi manifest + lockfile) and **setup scripts** only.
Large binaries, cloned repos, caches, and experiment outputs are intentionally ignored.

---

## Requirements

- OS: Ubuntu 22.04
- `git`
- `pixi` installed  ([Installation guide](https://pixi.prefix.dev/latest/installation/))


GPU drivers / CUDA runtime should be installed according to your machine.

---

## Quick Start

### unitree-rl-lab environment

1) Install
```bash
pixi install -e unitree-rl-lab
```

2) IsaacLab setup
```bash
pixi run -e unitree-rl-lab isaaclab-setup
```

3) rsl_rl setup
```bash
pixi run -e unitree-rl-lab rsl-rl-setup
```

4) VSCode setup
```bash
pixi run -e unitree-rl-lab vscode-setup
```

5) Unitree setup (clone + patch + editable install)
```bash
pixi run -e unitree-rl-lab unitree-setup
```

### unitree-mujoco environment

1) Install
```bash
pixi install -e unitree-mujoco
```

2) One-shot setup (apt deps + sdk2 + sdk2py + mujoco download + build)
```bash
pixi run -e unitree-mujoco unitree-mujoco-setup
```

3) Run the Python simulator
```bash
pixi run -e unitree-mujoco sim
```

#### Offline / Local Wheels via wheelhouse/
If you want to reduce downloads (or install in a limited-network environment), you can provide
pre-downloaded Python wheels in a local wheelhouse/ directory and enable find-links in pixi.toml.

In pixi.toml:
```toml
[pypi-options]
# Uncomment to use local wheels from ./wheelhouse
# find-links = [{ path = "./wheelhouse" }]
```
