import { useEffect, useRef } from "react";
import * as Tone from "tone";
import { playJianpu } from "@/utils/praseJianpuToken";
// usePlayRequestAutoplay.ts
function getContentObject(msg: any) {
  const c =
    msg?.payload?.content?.content ??
    msg?.payload?.content ??
    msg?.content?.content ??
    msg?.content ??
    null;

  return c && typeof c === "object" ? c : null;
}

export function usePlayRequestAutoplay(messages: any[]) {
  const lastPlayedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!messages?.length) return;

    const found = [...messages].reverse().find((msg) => {
      const text = typeof msg?.content === "string" ? msg.content : "";
      return text.startsWith("PLAY_REQUEST_JSON:");
    });

    if (!found) return;

    const msgId = found.event_id || found.message_id || found.id || null;
    if (msgId && lastPlayedIdRef.current === msgId) return;
    lastPlayedIdRef.current = msgId || "no-id";

    const text = typeof found?.content === "string" ? found.content : "";
    if (!text.startsWith("PLAY_REQUEST_JSON:")) return;

    let obj: any = null;
    try {
      obj = JSON.parse(text.slice("PLAY_REQUEST_JSON:".length));
    } catch (e) {
      console.error("[play_request] JSON parse failed:", e, "text=", text);
      return;
    }

    console.log("[play_request] received obj:", obj);

    const jianpu = String(obj.jianpu || "");
    const bpm = Number(obj.bpm ?? 90);
    const noteLen = Number(obj.note_len_beats ?? obj.noteLenBeats ?? 0.5);
    const instrument = String(obj.instrument || "piano");
    if (!jianpu) return;

    (async () => {
      if (Tone.getContext().state !== "running") {
        await Tone.start();
        await Tone.getContext().resume();
      }

//       const normalized = jianpu.replace(/,/g, " ").replace(/\s+/g, " ").trim();
     // console.log("[play_request] playing:", { instrument, bpm, noteLen, normalized });


     await playJianpu(jianpu, 90, 0.5, "violin", { style: "swing", accompaniment: "backbeat" });
    })().catch((e) => console.error("[play_request] playback failed:", e));
  }, [messages]);
}






export function useAutoplayWhenMusicWorkerResultArrives(messages: any[]) {
  const unlockedRef = useRef(false);
  const queuedRef = useRef<{ jianpu: string; bpm: number; noteLen: number } | null>(null);
  const lastPlayedMsgIdRef = useRef<string | null>(null);


  useEffect(() => {
    const unlock = async (e: Event) => {
      console.log("[autoplay] unlock fired:", e.type, "state(before)=", Tone.getContext().state);

      if (unlockedRef.current) return;

      try {
        await Tone.start();
        await Tone.getContext().resume();

        console.log("[autoplay] state(after)=", Tone.getContext().state);

        if (Tone.getContext().state !== "running") {
          console.log("[autoplay] still not running, wait next gesture");
          return;
        }

        unlockedRef.current = true;


//         const test = new Tone.Synth().toDestination();
//         test.triggerAttackRelease("C5", "8n");
//         setTimeout(() => test.dispose(), 300);

        if (queuedRef.current) {
          console.log("[autoplay] playing queued jianpu");
          const q = queuedRef.current;
          queuedRef.current = null;
          console.log("[play_request] jianpu raw =", q.jianpu);
          await playJianpu(q.jianpu, q.bpm, q.noteLen);
        }
      } catch (err) {
        console.log("[autoplay] unlock failed:", err);
      }
    };

    document.addEventListener("pointerdown", unlock, true);
    document.addEventListener("keydown", unlock, true);
    document.addEventListener("touchstart", unlock, true);

    return () => {
      document.removeEventListener("pointerdown", unlock, true);
      document.removeEventListener("keydown", unlock, true);
      document.removeEventListener("touchstart", unlock, true);
    };
  }, []);
const getMsgText = (msg: any) => {

  const t =
    msg?.payload?.content?.message ??
    msg?.content?.message ??
    msg?.payload?.message ??
    msg?.message ??
    msg?.payload?.content?.text ??
    msg?.content?.text ??
    msg?.content ??
    msg?.text;


  if (typeof msg?.payload?.content === "string") return msg.payload.content;
  if (typeof msg?.content === "string") return msg.content;

  return typeof t === "string" ? t : "";
};

useEffect(() => {
  console.log("[autoplay] messages changed, len=", messages?.length);
  if (!messages?.length) return;


  const last8 = messages.slice(-8).map((m: any) => ({
    id: m.event_id || m.message_id || m.id,
    sender: m.source_id || m.senderId || m.sender_id || m.author,
    text: getMsgText(m),
    rawContent: m?.payload?.content ?? m?.content,
  }));
  console.log("[autoplay] last8 parsed =", last8);

  const found = [...messages].reverse().find((msg) => /numbered notation[:：]/.test(getMsgText(msg)));
  console.log("[autoplay] found jianpu msg?", !!found);

  if (!found) return;

  const msgId = found.event_id || found.message_id || found.id || null;
  if (msgId && lastPlayedMsgIdRef.current === msgId) return;

  const text = getMsgText(found);
  const m = text.match(/numbered notation[:：]\s*([\s\S]+)$/);
  console.log("[autoplay] regex matched?", !!m, "text=", text);
  if (!m) return;

  const jianpu = m[1].trim();
  lastPlayedMsgIdRef.current = msgId || "no-id";
  console.log("[play_request] jianpu raw =", jianpu);
  (async () => {
    if (unlockedRef.current && Tone.getContext().state === "running") {
     await playJianpu(jianpu, 90, 0.5, "violin", { style: "swing", accompaniment: "backbeat" })
    } else {
      queuedRef.current = { jianpu, bpm: 90, noteLen: 0.5 };
      console.log("[autoplay] queued jianpu (waiting gesture)");
    }
  })();
}, [messages]);

}
