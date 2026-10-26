// Input: phone (left-thumb virtual joystick, drag-to-look on the right) and desktop (WASD + pointer-lock mouse).
export class Input {
  constructor(canvas, walker, { onUserMove } = {}) {
    this.canvas = canvas; this.walker = walker; this.onUserMove = onUserMove ?? (() => {});
    this.keys = new Set();
    this.joy = null; this.look = null;
    this.enabled = true;
    this.joyEl = document.getElementById('kz-joy');
    this.knob = this.joyEl.querySelector('.knob');
    this.lookSens = 0.0042; this.mouseSens = 0.0022;
    this.bind();
  }
  bind() {
    const c = this.canvas;
    addEventListener('keydown', (e) => {
      if (e.target instanceof HTMLInputElement) return;
      this.keys.add(e.code);
      if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) this.onUserMove();
    });
    addEventListener('keyup', (e) => this.keys.delete(e.code));
    addEventListener('blur', () => this.keys.clear());
    c.addEventListener('click', () => {
      if (!this.enabled || this.isTouch) return;
      if (document.pointerLockElement !== c) c.requestPointerLock?.()?.catch?.(() => {});
    });
    addEventListener('mousemove', (e) => {
      if (!this.enabled || document.pointerLockElement !== c) return;
      this.turn(e.movementX * this.mouseSens, e.movementY * this.mouseSens);
    });
    c.addEventListener('touchstart', (e) => this.touchStart(e), { passive: false });
    c.addEventListener('touchmove', (e) => this.touchMove(e), { passive: false });
    c.addEventListener('touchend', (e) => this.touchEnd(e), { passive: false });
    c.addEventListener('touchcancel', (e) => this.touchEnd(e), { passive: false });
  }
  get isTouch() { return this._touchSeen === true; }
  turn(dx, dy) {
    const w = this.walker;
    if (w.fixed) this.onUserMove();
    w.yaw -= dx;
    w.pitch = Math.max(-1.45, Math.min(1.45, w.pitch - dy));
  }
  touchStart(e) {
    this._touchSeen = true;
    if (!this.enabled) return;
    e.preventDefault();
    for (const t of e.changedTouches) {
      if (!this.joy && t.clientX < innerWidth * 0.45) {
        this.joy = { id: t.identifier, x0: t.clientX, y0: t.clientY, x: 0, y: 0 };
        this.joyEl.style.display = 'block';
        this.joyEl.style.left = `${t.clientX}px`; this.joyEl.style.top = `${t.clientY}px`;
        this.knob.style.transform = 'translate(0px, 0px)';
      } else if (!this.look) {
        this.look = { id: t.identifier, x: t.clientX, y: t.clientY };
      }
    }
  }
  touchMove(e) {
    if (!this.enabled) return;
    e.preventDefault();
    for (const t of e.changedTouches) {
      if (this.joy && t.identifier === this.joy.id) {
        let dx = t.clientX - this.joy.x0, dy = t.clientY - this.joy.y0;
        const R = 50, l = Math.hypot(dx, dy);
        if (l > R) { dx *= R / l; dy *= R / l; }
        this.joy.x = dx / R; this.joy.y = -dy / R;
        this.knob.style.transform = `translate(${dx}px, ${dy}px)`;
        this.onUserMove();
      } else if (this.look && t.identifier === this.look.id) {
        const dx = t.clientX - this.look.x, dy = t.clientY - this.look.y;
        this.look.x = t.clientX; this.look.y = t.clientY;
        this.turn(dx * this.lookSens, dy * this.lookSens);
      }
    }
  }
  touchEnd(e) {
    for (const t of e.changedTouches) {
      if (this.joy && t.identifier === this.joy.id) { this.joy = null; this.joyEl.style.display = 'none'; }
      if (this.look && t.identifier === this.look.id) this.look = null;
    }
  }
  update() {
    const k = this.keys, inp = this.walker.input;
    let x = 0, y = 0;
    if (this.enabled) {
      if (k.has('KeyW') || k.has('ArrowUp')) y += 1;
      if (k.has('KeyS') || k.has('ArrowDown')) y -= 1;
      if (k.has('KeyD')) x += 1;
      if (k.has('KeyA')) x -= 1;
      if (k.has('ArrowLeft')) this.turn(-0.03, 0);
      if (k.has('ArrowRight')) this.turn(0.03, 0);
      if (this.joy) {
        // dead zone, then a soft curve; full deflection runs
        const m = Math.hypot(this.joy.x, this.joy.y);
        const s = m < 0.12 ? 0 : Math.min(1, (m - 0.12) / 0.88);
        if (m > 0) { x += (this.joy.x / m) * s; y += (this.joy.y / m) * s; }
      }
    }
    inp.x = x; inp.y = y;
    inp.run = k.has('ShiftLeft') || k.has('ShiftRight') || (this.joy ? Math.hypot(this.joy.x, this.joy.y) > 0.97 : false);
    inp.active = x !== 0 || y !== 0;
  }
}
