import { Button } from "@heroui/react";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { ChatIcon, CloseIcon, SendIcon } from "@/components/icons";
import { COPILOT_MAX_MESSAGE, COPILOT_WIDTH, PANEL_WIDTH } from "@/constants/app.constant";
import { ask, retry } from "@/core/assistant/conversation";
import { ASSISTANT_MODE } from "@/enums/assistant.enum";
import { useCopilotStore } from "@/state/copilot.store";
import { usePanelStore } from "@/state/panel.store";
import type { Assistant } from "@/types/assistant.type";
import { CopilotMessages, sourceLabel } from "./CopilotMessages";
import "./copilot.css";

/** The demo's sample products: P003 is out on the shelf with stock in the backroom; P017 is not in the demo store. */
const DEMO_SKU = "P003";
const MISSING_SKU = "P017";

/** Prompts to start from, for the twin the Copilot talks about. */
function useSamples(assistant: Assistant | null): string[] {
  const { t } = useTranslation();
  if (!assistant) return [];
  if (assistant.mode === ASSISTANT_MODE.Demo) {
    return [
      t("copilot.samples.explain", { sku: DEMO_SKU }),
      t("copilot.samples.plan", { sku: DEMO_SKU }),
      t("copilot.samples.approve"),
      t("copilot.samples.explain", { sku: MISSING_SKU }),
    ];
  }
  return [t("copilot.samples.explain", { sku: MISSING_SKU }), t("copilot.samples.plan", { sku: MISSING_SKU })];
}

/** The chip under the title: the demo script, or Live and, once one has answered, the model behind it. */
function SourceChip({ assistant }: { assistant: Assistant | null }) {
  const { t } = useTranslation();
  const lastTurn = useCopilotStore((state) => {
    for (let index = state.messages.length - 1; index >= 0; index -= 1) {
      const message = state.messages[index];
      if (message.kind === "reply") return message.turn;
    }
    return null;
  });
  if (!assistant) return <span className="copilot-source">{t("copilot.source.none")}</span>;
  if (assistant.mode === ASSISTANT_MODE.Demo) {
    return (
      <span className="copilot-source" data-source="demo_script" title={t("copilot.source.demoHint")}>
        {t("copilot.source.demo")}
      </span>
    );
  }
  return (
    <span className="copilot-source" data-source={lastTurn?.source ?? "live"} title={t("copilot.source.liveHint")}>
      {lastTurn ? sourceLabel(lastTurn, t) : t("copilot.source.live")}
    </span>
  );
}

/**
 * The Store Copilot (#332): a conversation beside the Agent Activity panel, which it never
 * replaces. It reads the store and opens plans as simulations through `assistant`; it never
 * writes the Live Twin, and approval stays with the Simulation banner. Its tool calls show in
 * the Agent Activity timeline. Enter sends, Shift+Enter breaks the line, Escape closes it.
 */
export function CopilotDrawer({ assistant }: { assistant: Assistant | null }) {
  const { t } = useTranslation();
  const open = useCopilotStore((state) => state.open);
  const setOpen = useCopilotStore((state) => state.setOpen);
  const messages = useCopilotStore((state) => state.messages);
  const pending = useCopilotStore((state) => state.pending);
  // Sit left of the floating Agent Activity panel instead of under it.
  const panelInset = usePanelStore((state) => (state.open ? PANEL_WIDTH + 24 : 0));
  const samples = useSamples(assistant);
  const [text, setText] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const list = useRef<HTMLOListElement>(null);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  // Keep the latest message in view.
  useEffect(() => {
    const node = list.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, pending]);

  const send = (value: string) => {
    if (!value.trim() || pending) return;
    setText("");
    void ask(assistant, value);
  };
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    send(text);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send(text);
    }
  };
  const note = !assistant ? "copilot.note.none" : assistant.mode === ASSISTANT_MODE.Demo ? "copilot.note.demo" : "copilot.note.live";

  return (
    <AnimatePresence>
      {open ? (
        <motion.aside
          key="copilot"
          id="copilot"
          className="copilot"
          data-testid="copilot"
          data-mode={assistant?.mode ?? "none"}
          aria-labelledby="copilot-title"
          style={{ width: COPILOT_WIDTH, marginRight: panelInset }}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
        >
          <header className="copilot-head">
            <span className="copilot-mark">
              <ChatIcon className="h-4 w-4" />
            </span>
            <div className="copilot-heading">
              <h2 id="copilot-title">{t("copilot.title")}</h2>
              <SourceChip assistant={assistant} />
            </div>
            <Button
              isIconOnly
              size="sm"
              variant="light"
              radius="sm"
              aria-label={t("copilot.close")}
              title={t("copilot.close")}
              onPress={() => setOpen(false)}
              className="ml-auto min-w-0 cursor-pointer text-ink-muted data-[hover=true]:bg-card data-[hover=true]:text-ink"
            >
              <CloseIcon className="h-4 w-4" />
            </Button>
          </header>
          <p className="copilot-note" data-mode={assistant?.mode ?? "none"}>
            {t(note)}
          </p>

          <ol ref={list} className="copilot-messages" aria-label={t("copilot.label")} aria-live="polite" aria-busy={pending !== null}>
            {messages.length === 0 ? (
              <li className="copilot-empty">
                <p>{t("copilot.intro")}</p>
                {samples.length ? (
                  <div className="copilot-samples" role="group" aria-label={t("copilot.samples.label")}>
                    {samples.map((sample) => (
                      <button key={sample} type="button" onClick={() => send(sample)}>
                        {sample}
                      </button>
                    ))}
                  </div>
                ) : null}
              </li>
            ) : (
              <CopilotMessages messages={messages} busy={pending !== null} onRetry={(messageId) => void retry(assistant, messageId)} />
            )}
            {pending ? (
              <li className="copilot-message" data-kind="pending" role="status">
                <span className="copilot-dots" aria-hidden />
                {t("copilot.thinking")}
              </li>
            ) : null}
          </ol>

          <form className="copilot-compose" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="copilot-input">
              {t("copilot.input")}
            </label>
            <textarea
              id="copilot-input"
              ref={input}
              className="text-field copilot-input"
              rows={2}
              maxLength={COPILOT_MAX_MESSAGE}
              value={text}
              placeholder={t("copilot.placeholder", { sku: assistant?.mode === ASSISTANT_MODE.Demo ? DEMO_SKU : MISSING_SKU })}
              aria-describedby="copilot-hint"
              onChange={(event) => setText(event.target.value)}
              onKeyDown={onKeyDown}
            />
            <Button
              type="submit"
              isIconOnly
              color="secondary"
              aria-label={t("copilot.send")}
              title={t("copilot.send")}
              isDisabled={!text.trim() || pending !== null}
              className="h-9 w-9 min-w-0"
            >
              <SendIcon className="h-4 w-4" />
            </Button>
          </form>
          <p id="copilot-hint" className="copilot-hint">
            {t("copilot.hint")}
          </p>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}

/** The header's Copilot button: opens and closes the drawer. */
export function CopilotButton() {
  const { t } = useTranslation();
  const open = useCopilotStore((state) => state.open);
  const toggle = useCopilotStore((state) => state.toggle);
  return (
    <button
      type="button"
      className="twin-header-copilot"
      aria-expanded={open}
      aria-controls="copilot"
      title={t("copilot.openHint")}
      onClick={toggle}
    >
      <ChatIcon className="h-3.5 w-3.5" />
      {t("copilot.open")}
    </button>
  );
}
