import * as Tone from "tone";

const DEGREE_TO_SEMITONE: Record<string, number> = {
  "1": 0,  // C
  "2": 2,  // D
  "3": 4,  // E
  "4": 5,  // F
  "5": 7,  // G
  "6": 9,  // A
  "7": 11, // B
};

function countChar(s: string, ch: string) {
  return (s.match(new RegExp(`\\${ch}`, "g")) || []).length;
}




export type PlayStyle = "straight" | "accented" | "swing";
export type Accompaniment = "none" | "alberti" | "backbeat";

export interface PlayOptions {
  style?: PlayStyle;                 // 三套节奏/强弱方案
  accompaniment?: Accompaniment;     // 三套伴奏方案
  accentStrongMul?: number;          // 强拍音量倍率
  accentWeakMul?: number;            // 弱拍音量倍率
  swingShort?: number;               // swing 短音占比（0~1）
  swingLong?: number;                // swing 长音占比（0~1）
}

// 统一生成“每个音符的时值(beat) + 音量(velocity 0~1)”


function getNotePlan(
  style: PlayStyle,
  i: number,
  baseBeats: number,
  opt: Required<Pick<PlayOptions, "accentStrongMul" | "accentWeakMul" | "swingShort" | "swingLong">>
) {
  if (style === "straight") {
    return { beats: baseBeats, vel: 0.9 };
  }

  if (style === "accented") {
    // 方案 1：强弱拍
    const beatInBar = i % 4; // 0,1,2,3
    const isStrong = beatInBar === 0 || beatInBar === 2;
    const vel = isStrong ? 0.9 * opt.accentStrongMul : 0.9 * opt.accentWeakMul;
    return { beats: baseBeats, vel: Math.max(0.05, Math.min(1, vel)) };
  }

  // style === "swing"
  // 方案 2：短-长
  const isFirstInPair = i % 2 === 0;
  const beats = isFirstInPair ? baseBeats * opt.swingShort : baseBeats * opt.swingLong;
  const vel = isFirstInPair ? 0.85 : 0.95; // 长音略强一点更像“落点”
  return { beats, vel };
}

// 伴奏
function createAccompSynth() {
  return new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "triangle" },
    envelope: { attack: 0.005, decay: 0.08, sustain: 0.6, release: 0.35 },
    volume: -1,
  }).toDestination();
}

// 根据“当前主旋律音高”给一个非常保守的和弦/低音
function pickBassMidiFromMelody(midi: number) {
  // 低一到两组八度作为低音
  return midi - 24;
}

async function playAccompanimentOneShot(
  accompaniment: Accompaniment,
  t: number,
  durSec: number,
  melodyMidi: number,
  accompSynth: Tone.PolySynth
) {
  if (accompaniment === "none") return;

  const bassMidi = pickBassMidiFromMelody(melodyMidi);
  const bassNote = Tone.Frequency(bassMidi, "midi").toNote();

  if (accompaniment === "alberti") {
    // 方案 A：Alberti-ish：
    accompSynth.triggerAttackRelease(bassNote, durSec * 0.9, t, 0.5);
    const upper = Tone.Frequency(bassMidi + 7, "midi").toNote(); // 纯五度
    accompSynth.triggerAttackRelease(upper, durSec * 0.6, t + durSec * 0.4, 0.35);
    return;
  }

  if (accompaniment === "backbeat") {
    // 方案 B：反拍（简化）：
    const chord = Tone.Frequency(bassMidi + 12, "midi").toNote(); // 高八度点一下
    accompSynth.triggerAttackRelease(chord, durSec * 0.25, t + durSec * 0.5, 0.25);
    return;
  }
}









export function parseJianpuToken(token: string) {

  token = token
  .trim()
  .replace(/，/g, ",")   // 中文逗号 -> 英文逗号（低八度）
  .replace(/\u0323/g, ",")
  .replace(/＇/g, "'")   // 全角撇号 -> 英文撇号（高八度）
  .replace(/♯/g, "#")   // 全角 # -> #
  .replace(/♭/g, "b");  // 全角 b -> b
  if (!token) return null;




  // 八度偏移：, 低八度；. 高八度（支持多个）
  const downOct = countChar(token, ",");
  const upOct = countChar(token, "'");

  // 升降号：支持多个 # 或多个 b（叠加半音）
  const sharps = countChar(token, "#");
  const flats = countChar(token, "b");

  // 找到 1-7
  const m = token.match(/[1-7]/);
  if (!m) return null;
  const degree = m[0];

  const base = DEGREE_TO_SEMITONE[degree];

  // 以 C4 为 1（do）基准：C4 = MIDI 60
  const semitoneFromC4 =
    base + sharps - flats + (upOct - downOct) * 12;

  const midi = 60 + semitoneFromC4;

  const hasAccidental = sharps > 0 || flats > 0;
  return { midi, rest: false, hasAccidental };
}

function createInstrumentSynth(instrument?: string) {
  const inst = (instrument || "piano").toLowerCase();

  switch (inst) {
    case "guitar": {

      const s = new Tone.PluckSynth({
        attackNoise: 1.0,
        dampening: 2500,
        resonance: 0.9,
      }).toDestination();
      return s;
    }

    case "violin": {

      const synth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sawtooth" },
        envelope: { attack: 0.15, decay: 0.2, sustain: 0.8, release: 0.6 },
      });

      const filter = new Tone.Filter(1800, "lowpass").toDestination();
      synth.connect(filter);

      const lfo = new Tone.LFO({ frequency: 5, min: -15, max: 15 }).start();
      const target: any = (synth as any)?.detune ?? (synth as any)?.frequency;
    if (target) {
      lfo.connect(target);
    } else {
      console.warn("[createInstrumentSynth] LFO target missing for", instrument, synth);
    }



      (synth as any).__lfo = lfo;
      (synth as any).__out = filter;

      return synth;
    }

    case "bagpipe": {

      const synth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "square" },
        envelope: { attack: 0.05, decay: 0.0, sustain: 1.0, release: 0.4 },
      });

      const bp = new Tone.Filter({ type: "bandpass", frequency: 900, Q: 5 }).toDestination();
      synth.connect(bp);
      (synth as any).__out = bp;

      return synth;
    }

    case "organ": {

      return new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine" },
        envelope: { attack: 0.01, decay: 0.0, sustain: 1.0, release: 0.2 },
      }).toDestination();
    }

    case "trumpet": {
      // 小号：更亮、更硬（saw + 过滤器 + 更快 attack）
      const synth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sawtooth" },
        envelope: { attack: 0.02, decay: 0.15, sustain: 0.5, release: 0.25 },
      });

      const hp = new Tone.Filter(600, "highpass").toDestination();
      synth.connect(hp);
      (synth as any).__out = hp;

      return synth;
    }

    case "flute": {
      // 长笛
      const synth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "triangle" },
        envelope: { attack: 0.06, decay: 0.1, sustain: 0.7, release: 0.4 },
      });

      const lp = new Tone.Filter(1200, "lowpass").toDestination();
      synth.connect(lp);
      (synth as any).__out = lp;

      return synth;
    }

    case "piano":
    default: {
      // 钢琴
      return new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "triangle" },
        envelope: { attack: 0.005, decay: 0.25, sustain: 0.5, release: 0.2 },
      }).toDestination();
    }
  }
}
export async function playJianpu(
  jianpu: string,
  bpm = 90,
  noteLenBeats = 0.5,
  instrument: string = "piano",
   options: PlayOptions = { }
) {
  // Ensure audio context
  if (Tone.getContext().state !== "running") {
    await Tone.start();
    await Tone.getContext().resume();
  }
//   console.log("[playJianpu] tokens =", jianpu);
  // Do NOT remove commas: commas mean octave-down in your notation
  const normalized = (jianpu || "").replace(/\s+/g, " ").trim();

  const synth = createInstrumentSynth(instrument);

  const tokens = normalized
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean);
//   console.log("[playJianpu] tokens =", tokens);
  const secondsPerBeat = 60 / (bpm || 90);
  const baseBeats = noteLenBeats || 0.5;

  const style: PlayStyle = options.style ?? "straight";
  const accompaniment: Accompaniment = options.accompaniment ?? "none";

  const optNormalized = {
    accentStrongMul: options.accentStrongMul ?? 1.15,
    accentWeakMul: options.accentWeakMul ?? 0.85,
    swingShort: options.swingShort ?? 0.7,
    swingLong: options.swingLong ?? 1.3,
  } as const;


  const accompSynth = accompaniment === "none" ? null : createAccompSynth();

  let t = Tone.now() + 0.05;
  let noteIndex = 0;

  for (const tok of tokens) {
    const parsed = parseJianpuToken(tok) as any;

    //  style 生成 beats + velocity
    const plan = getNotePlan(style, noteIndex, baseBeats, optNormalized);
    const durSec = plan.beats * secondsPerBeat;

    if (!parsed || parsed.rest) {
      t += durSec;
      noteIndex += 1;
      continue;
    }

    const note = Tone.Frequency(parsed.midi, "midi").toNote();

    // 主旋律
    synth.triggerAttackRelease(note, durSec, t, plan.vel);

    // 伴奏
    if (accompSynth) {
      await playAccompanimentOneShot(accompaniment, t, durSec, parsed.midi, accompSynth);
    }

    t += durSec;
    noteIndex += 1;
  }

  // Dispose synth after playback
  const ms = Math.max(200, (t - Tone.now()) * 1000 + 150);
  setTimeout(() => {
    synth.dispose();
    accompSynth?.dispose();
  }, ms);

}
