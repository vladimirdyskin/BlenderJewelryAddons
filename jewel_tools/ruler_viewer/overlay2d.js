// 2D dimension overlay — port of the Pretty Ruler POST_PIXEL draw callback.
// All geometry runs in Blender's region space (CSS px, Y UP, origin bottom-left);
// the y-flip to canvas space happens only inside the drawing primitives.

export const DEFAULT_STYLE = {
  endcap: 'ARROW',
  tickLength: 14,
  arrowSize: 12,
  lineWidth: 2,
  fontSize: 18,
  decimals: 2,
  unitSuffix: ' mm',
  smallLeaderLength: 45,
  textGap: 6,
  extensionLines: false,
  extOffset: 40,
  extGap: 6,
  extAutoSide: true,
  arcRadius: 40,
  lineColor: [1, 1, 1, 1],
  textColor: [1, 1, 1, 1],
  bgColor: [0, 0, 0, 0.6],
  textBg: true,
  linkColor: [1.0, 0.6, 0.1, 1],
};

// ---- Vector helpers (mathutils.Vector subset) ----
const V = (x, y) => ({ x, y });
const add = (a, b) => V(a.x + b.x, a.y + b.y);
const sub = (a, b) => V(a.x - b.x, a.y - b.y);
const mul = (a, s) => V(a.x * s, a.y * s);
const neg = (a) => V(-a.x, -a.y);
const length = (a) => Math.hypot(a.x, a.y);
const normalized = (a) => { const l = length(a); return l ? V(a.x / l, a.y / l) : V(0, 0); };
// `v.normalized() if v.length else Vector((1, 0))`
const unitOrX = (a) => (length(a) ? normalized(a) : V(1, 0));

const rgba = (c) => `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${c.length > 3 ? c[3] : 1})`;
const font = (size) => `${size}px system-ui, -apple-system, sans-serif`;

// ---- Drawing primitives: the only place where Y is flipped ----
function line(g, a, b, color, width) {
  const ctx = g.ctx;
  ctx.strokeStyle = rgba(color);
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(a.x, g.H - a.y);
  ctx.lineTo(b.x, g.H - b.y);
  ctx.stroke();
}

function polyline(g, points, color, width) {
  if (points.length < 2) return;
  const ctx = g.ctx;
  ctx.strokeStyle = rgba(color);
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(points[0].x, g.H - points[0].y);
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, g.H - points[i].y);
  ctx.stroke();
}

// Filled convex polygon (TRIS batch equivalent; a quad is drawn as one path to avoid an AA seam).
function tris(g, points, color) {
  const ctx = g.ctx;
  ctx.fillStyle = rgba(color);
  ctx.beginPath();
  ctx.moveTo(points[0].x, g.H - points[0].y);
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, g.H - points[i].y);
  ctx.closePath();
  ctx.fill();
}

// blf.position(baseline-left) + blf.rotation(ang, CCW in y-up) + blf.draw
function text(g, str, start, ang, size, color) {
  const ctx = g.ctx;
  ctx.save();
  ctx.translate(start.x, g.H - start.y);
  if (ang) ctx.rotate(-ang); // CCW in y-up space is CW on the y-down canvas
  ctx.font = font(size);
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = rgba(color);
  ctx.fillText(str, 0, 0);
  ctx.restore();
}

// blf.dimensions -> [width, height]
function textDims(g, str, size) {
  const ctx = g.ctx;
  ctx.font = font(size);
  const m = ctx.measureText(str);
  const h = (m.actualBoundingBoxAscent || 0) + (m.actualBoundingBoxDescent || 0);
  return [m.width, h || size * 0.72];
}

// ---- Ported functions (names mirror the Python originals) ----
function arrowOutward(g, tip, outwardUnit, size, color) {
  const d = unitOrX(outwardUnit);
  const perp = V(-d.y, d.x);
  const base = sub(tip, mul(d, size));
  tris(g, [tip, add(base, mul(perp, size * 0.45)), sub(base, mul(perp, size * 0.45))], color);
}

function arrowInward(g, tip, outwardUnit, size, color) {
  const d = unitOrX(outwardUnit);
  const perp = V(-d.y, d.x);
  const base = add(tip, mul(d, size));
  tris(g, [tip, add(base, mul(perp, size * 0.45)), sub(base, mul(perp, size * 0.45))], color);
}

function endcap(g, pt, outwardDir, color) {
  const s = g.style;
  const d = unitOrX(outwardDir);
  const perp = V(-d.y, d.x);
  if (s.endcap === 'TICK') {
    const L = s.tickLength;
    line(g, add(pt, mul(perp, L * 0.5)), sub(pt, mul(perp, L * 0.5)), color, s.lineWidth);
  } else if (s.endcap === 'ARROW') {
    arrowOutward(g, pt, d, s.arrowSize, color);
  }
}

function bgQuadAxis(g, center, dr, up, hw, hh) {
  const s = g.style;
  if (!s.textBg) return;
  const c00 = sub(sub(center, mul(dr, hw)), mul(up, hh));
  const c10 = sub(add(center, mul(dr, hw)), mul(up, hh));
  const c11 = add(add(center, mul(dr, hw)), mul(up, hh));
  const c01 = add(sub(center, mul(dr, hw)), mul(up, hh));
  tris(g, [c00, c10, c11, c01], s.bgColor);
}

// Horizontal centered text with optional background.
function drawTextH(g, pos2d, str) {
  const s = g.style;
  const [tw, th] = textDims(g, str, s.fontSize);
  if (s.textBg) {
    const pad = 4;
    bgQuadAxis(g, pos2d, V(1, 0), V(0, 1), tw * 0.5 + pad, th * 0.5 + pad);
  }
  text(g, str, V(pos2d.x - tw * 0.5, pos2d.y - th * 0.5), 0, s.fontSize, s.textColor);
}

// Text centered, rotated to run along lineDir, sitting above the line.
function drawTextAlong(g, center, lineDir, str) {
  const s = g.style;
  const d = unitOrX(lineDir);
  let ang = Math.atan2(d.y, d.x);
  // keep upright/readable
  if (ang > Math.PI / 2) ang -= Math.PI;
  else if (ang < -Math.PI / 2) ang += Math.PI;
  const dr = V(Math.cos(ang), Math.sin(ang));
  let up = V(-dr.y, dr.x);
  if (up.y < 0) up = neg(up);
  const [tw, th] = textDims(g, str, s.fontSize);
  // place above the line
  const textCenter = add(center, mul(up, s.textGap + th * 0.5));
  // background (rotated)
  const pad = 4;
  bgQuadAxis(g, textCenter, dr, up, tw * 0.5 + pad, th * 0.5 + pad);
  // baseline start so glyphs center on textCenter
  const start = sub(sub(textCenter, mul(dr, tw * 0.5)), mul(up, th * 0.5));
  text(g, str, start, ang, s.fontSize, s.textColor);
}

// view3d_utils.location_3d_to_region_2d: project -> y-up region coords (or null)
function toRegion2d(g, p3d) {
  const p = g.project(p3d);
  return p ? V(p.x, g.H - p.y) : null;
}

// Screen vector from the projected world origin to the point; null if the origin is not projectable.
function awayFromCenter(g, pt2d) {
  return g.origin2d ? sub(pt2d, g.origin2d) : null;
}

function drawDistance(g, dim) {
  const s = g.style;
  const [a3d, b3d] = dim.points;
  const a2d = toRegion2d(g, a3d);
  const b2d = toRegion2d(g, b3d);
  if (!a2d || !b2d) return;
  const color = s.lineColor;
  const direction = sub(b2d, a2d);
  if (length(direction) === 0) return;
  const perp = normalized(V(-direction.y, direction.x));

  // Dimension line endpoints (offset by extension lines if enabled)
  let P0, P1;
  if (s.extensionLines && s.extOffset !== 0) {
    let signedPerp = perp;
    let mag;
    if (s.extAutoSide) {
      // away from the scene center on screen; center on the dimension axis -> up (vertical -> right)
      const away = awayFromCenter(g, mul(add(a2d, b2d), 0.5));
      let sd = away ? signedPerp.x * away.x + signedPerp.y * away.y : 0;
      if (Math.abs(sd) < 1.0) sd = signedPerp.y || signedPerp.x;
      if (sd < 0) signedPerp = neg(signedPerp);
      mag = Math.abs(s.extOffset);
    } else {
      mag = s.extOffset;
    }
    const off = mul(signedPerp, mag);
    const gap = mul(signedPerp, s.extGap);
    P0 = add(a2d, off);
    P1 = add(b2d, off);
    line(g, add(a2d, gap), P0, color, s.lineWidth);
    line(g, add(b2d, gap), P1, color, s.lineWidth);
  } else {
    P0 = a2d;
    P1 = b2d;
  }

  const label = dim.label;
  const d = normalized(sub(P1, P0));
  const [tw, th] = textDims(g, label, s.fontSize);
  // "small" when the text and the arrows do not fit between the ends on screen
  const caps = s.endcap === 'ARROW' ? 2 * s.arrowSize : 0;

  if (length(sub(P1, P0)) < tw + caps + 8) {
    // Small style: arrows outside pointing in, dimension line extended, leader + shelf + text
    const stub = Math.max(s.arrowSize, 8) * 1.4;
    const out0 = sub(P0, mul(d, stub));
    const out1 = add(P1, mul(d, stub));
    line(g, out0, out1, color, s.lineWidth);
    arrowInward(g, P0, neg(d), s.arrowSize, color);
    arrowInward(g, P1, d, s.arrowSize, color);
    // leader away from the scene center on screen
    const anchor = mul(add(P0, P1), 0.5);
    const away = awayFromCenter(g, anchor);
    const side = away && away.x < 0 ? -1 : 1;
    const diag = normalized(V(side, 1));
    const elbow = add(anchor, mul(diag, s.smallLeaderLength));
    const shelfLen = tw + 12;
    const shelfEnd = add(elbow, mul(V(side, 0), shelfLen));
    line(g, anchor, elbow, color, s.lineWidth);
    line(g, elbow, shelfEnd, color, s.lineWidth);
    // text above the shelf, centered over it
    const textCenter = add(mul(add(elbow, shelfEnd), 0.5), V(0, th * 0.5 + s.textGap));
    drawTextH(g, textCenter, label);
  } else {
    // Normal style: arrows/ticks at ends, text along axis above the line
    line(g, P0, P1, color, s.lineWidth);
    endcap(g, P0, sub(P0, P1), color);
    endcap(g, P1, sub(P1, P0), color);
    drawTextAlong(g, mul(add(P0, P1), 0.5), d, label);
  }
}

function drawAngle(g, dim) {
  const s = g.style;
  const [a3d, c3d, b3d] = dim.points;
  const a2d = toRegion2d(g, a3d);
  const c2d = toRegion2d(g, c3d);
  const b2d = toRegion2d(g, b3d);
  if (!a2d || !c2d || !b2d) return;
  const color = s.lineColor;
  line(g, c2d, a2d, color, s.lineWidth);
  line(g, c2d, b2d, color, s.lineWidth);
  const da = sub(a2d, c2d);
  const db = sub(b2d, c2d);
  if (length(da) === 0 || length(db) === 0) return;
  const aAng = Math.atan2(da.y, da.x);
  const bAng = Math.atan2(db.y, db.x);
  // Python's % keeps the sign of the divisor
  const twoPi = 2 * Math.PI;
  const diff = ((((bAng - aAng + Math.PI) % twoPi) + twoPi) % twoPi) - Math.PI;
  const R = s.arcRadius;
  const segs = 24;
  const arcPts = [];
  for (let i = 0; i <= segs; i++) {
    const t = aAng + diff * (i / segs);
    arcPts.push(add(c2d, mul(V(Math.cos(t), Math.sin(t)), R)));
  }
  polyline(g, arcPts, color, s.lineWidth);
  const midAng = aAng + diff * 0.5;
  const labelPos = add(c2d, mul(V(Math.cos(midAng), Math.sin(midAng)), R + s.fontSize));
  drawTextH(g, labelPos, dim.label);
}

export class DimensionOverlay {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.style = { ...DEFAULT_STYLE };
    this.dimensions = [];
    this.enabledOverride = new Map();
    this.visible = true;
    this.cssWidth = canvas.clientWidth || canvas.width;
    this.cssHeight = canvas.clientHeight || canvas.height;
    this.dpr = 1;
  }

  setData(dimensionsJson) {
    this.style = { ...DEFAULT_STYLE, ...((dimensionsJson && dimensionsJson.style) || {}) };
    this.dimensions = (dimensionsJson && dimensionsJson.dimensions) || [];
    this.enabledOverride.clear();
  }

  setEnabled(id, enabled) {
    this.enabledOverride.set(id, !!enabled);
  }

  isEnabled(dim) {
    return this.enabledOverride.has(dim.id) ? this.enabledOverride.get(dim.id) : dim.enabled !== false;
  }

  setVisible(visible) {
    this.visible = !!visible;
  }

  resize(cssWidth, cssHeight, dpr) {
    this.cssWidth = cssWidth;
    this.cssHeight = cssHeight;
    this.dpr = dpr || 1;
    this.canvas.width = Math.round(cssWidth * this.dpr);
    this.canvas.height = Math.round(cssHeight * this.dpr);
    this.canvas.style.width = cssWidth + 'px';
    this.canvas.style.height = cssHeight + 'px';
  }

  // draw_callback: project([x,y,z]) -> {x, y} in CSS px, y down (canvas), or null
  render(project) {
    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    if (!this.visible || !this.dimensions.length) return;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    const g = { ctx, H: this.cssHeight, style: this.style, project, origin2d: null };
    g.origin2d = toRegion2d(g, [0, 0, 0]);
    // _Recolor(props, props.link_color): linked dimensions use linkColor for lines and text
    const lc = this.style.linkColor;
    const gl = { ...g, style: { ...this.style, lineColor: lc, textColor: lc } };
    for (const dim of this.dimensions) {
      if (!this.isEnabled(dim)) continue;
      const gd = dim.linked ? gl : g;
      if (dim.type === 'distance' && dim.points.length === 2) drawDistance(gd, dim);
      else if (dim.type === 'angle' && dim.points.length === 3) drawAngle(gd, dim);
    }
  }
}
