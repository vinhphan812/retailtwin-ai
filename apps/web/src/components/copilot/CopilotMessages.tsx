import { Button } from "@heroui/react";
import { useTranslation } from "react-i18next";
import { RetryIcon } from "@/components/icons";
import { SkuChip, clock } from "@/components/layout/ActivityLog";
import { ASSISTANT_ERROR, ASSISTANT_SOURCE, ASSISTANT_STATUS } from "@/enums/assistant.enum";
import { format } from "@/core/utils/format";
import type { CopilotMessage } from "@/state/copilot.store";
import type { AssistantFailure, AssistantTurn } from "@/types/assistant.type";
import { CopilotProposal } from "./CopilotProposal";

/** Who wrote a reply, as its source and model say. */
export function sourceLabel(turn: Pick<AssistantTurn, "source" | "model">, t: ReturnType<typeof useTranslation>["t"]): string {
  if (turn.source === ASSISTANT_SOURCE.DemoScript) return t("copilot.source.demo");
  return turn.model ? t("copilot.source.geminiModel", { model: turn.model }) : t("copilot.source.gemini");
}

/** Every product a reply is about, in the order it names them. */
function productsOf(turn: AssistantTurn): string[] {
  const skus = [
    ...turn.evidence.map((item) => item.sku),
    ...(turn.proposal?.actions.map((action) => action.sku) ?? []),
    ...turn.tool_calls.map((call) => call.sku),
  ];
  return [...new Set(skus.filter((sku): sku is string => sku !== null))];
}

/** A label for a served code: the Copilot's own words when it knows the code, the code otherwise. */
function codeLabel(t: ReturnType<typeof useTranslation>["t"], prefix: "copilot.outcome" | "copilot.error", code: string): string {
  return t(`${prefix}.${code}` as never, { defaultValue: code }) as string;
}

/** What the evidence and tool lists show of one reply, folded until opened. */
function ReplyDetails({ turn }: { turn: AssistantTurn }) {
  const { t } = useTranslation();
  return (
    <>
      {turn.evidence.length ? (
        <details className="copilot-details">
          <summary>{t("copilot.evidence.title", { count: turn.evidence.length })}</summary>
          <ul>
            {turn.evidence.map((item) => (
              <li key={item.id}>
                <span className="copilot-details-label">{item.label}</span>
                <span>{item.detail}</span>
                <span className="copilot-details-meta">
                  <span className="copilot-source" data-source={item.source}>
                    {t(`copilot.evidence.source.${item.source}`)}
                  </span>
                  {item.as_of ? <span>{t("copilot.evidence.asOf", { time: item.as_of })}</span> : null}
                  {item.confidence !== null ? (
                    <span>{t("copilot.evidence.confidence", { value: format.percent(item.confidence) })}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {turn.tool_calls.length ? (
        <details className="copilot-details">
          <summary>{t("copilot.tools.title", { count: turn.tool_calls.length })}</summary>
          <ul>
            {turn.tool_calls.map((call, index) => (
              <li key={`${call.tool}:${index}`} className="copilot-tool" data-ok={call.ok}>
                <code>{call.tool}</code>
                {call.sku ? <span>{call.sku}</span> : null}
                <span className="copilot-details-meta">
                  {t(`copilot.tools.capability.${call.capability}`)} ·{" "}
                  {call.ok ? t("copilot.tools.ok") : t("copilot.tools.failed", { code: call.error_code ?? "" })}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </>
  );
}

/** One reply: its text, the products it names, its plan, its evidence and tools, and who wrote it on which Live state. */
function Reply({ turn }: { turn: AssistantTurn }) {
  const { t } = useTranslation();
  const products = productsOf(turn);
  const declined = turn.status === ASSISTANT_STATUS.Refused || turn.status === ASSISTANT_STATUS.Unsupported;
  return (
    <li className="copilot-message" data-kind="reply" data-status={turn.status}>
      {declined ? (
        <span className="copilot-outcome">
          {t(`copilot.status.${turn.status}`)}
          {turn.outcome_code ? ` · ${codeLabel(t, "copilot.outcome", turn.outcome_code)}` : ""}
        </span>
      ) : null}
      <p className="copilot-text">{turn.text}</p>
      {products.length ? (
        <div className="copilot-products" role="group" aria-label={t("copilot.products")}>
          {products.map((sku) => (
            <SkuChip key={sku} sku={sku} />
          ))}
        </div>
      ) : null}
      {turn.proposal ? <CopilotProposal proposal={turn.proposal} /> : null}
      <ReplyDetails turn={turn} />
      <p className="copilot-meta">
        <span className="copilot-source" data-source={turn.source}>
          {sourceLabel(turn, t)}
        </span>
        <time dateTime={turn.created_at}>{clock(turn.created_at)}</time>
        {turn.context_version ? <span>{t("copilot.meta.context", { version: turn.context_version })}</span> : null}
        <span className="copilot-meta-id" title={turn.correlation_id}>
          {t("copilot.meta.correlation", { id: turn.correlation_id })}
        </span>
      </p>
    </li>
  );
}

/** Why a message got no reply: what happened, its HTTP status and code, the correlation id to look it up by, and a retry. */
function Failure({ failure, at, onRetry, busy }: { failure: AssistantFailure; at: string; onRetry: () => void; busy: boolean }) {
  const { t } = useTranslation();
  const stale = failure.code === ASSISTANT_ERROR.StaleContext;
  const known = t(`copilot.error.${failure.code}` as never, { defaultValue: "" }) as string;
  return (
    <li className="copilot-message" data-kind="error" role="alert">
      <span className="copilot-outcome">{t("copilot.error.title")}</span>
      <p className="copilot-text">{known || t("copilot.error.request_failed")}</p>
      {failure.message && failure.message !== known ? <p className="copilot-error-detail">{failure.message}</p> : null}
      <p className="copilot-meta">
        <span>
          {failure.status
            ? t("copilot.error.meta", { status: failure.status, code: failure.code })
            : t("copilot.error.metaNoStatus", { code: failure.code })}
        </span>
        <time dateTime={at}>{clock(at)}</time>
        {failure.correlation_id ? (
          <span className="copilot-meta-id" title={failure.correlation_id}>
            {t("copilot.meta.correlation", { id: failure.correlation_id })}
          </span>
        ) : null}
      </p>
      {failure.retryable || stale ? (
        <Button
          size="sm"
          variant="bordered"
          className="self-start border-white/15 text-[var(--color-ink)]"
          startContent={<RetryIcon className="h-3.5 w-3.5" />}
          isDisabled={busy}
          onPress={onRetry}
        >
          {stale ? t("copilot.error.askAgain") : t("copilot.error.retry")}
        </Button>
      ) : null}
    </li>
  );
}

/** The conversation, oldest first. */
export function CopilotMessages({
  messages,
  busy,
  onRetry,
}: {
  messages: CopilotMessage[];
  busy: boolean;
  onRetry: (messageId: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      {messages.map((message) => {
        if (message.kind === "user") {
          return (
            <li key={message.id} className="copilot-message" data-kind="user">
              <span className="sr-only">{t("copilot.you")}: </span>
              <p className="copilot-text">{message.request.text}</p>
            </li>
          );
        }
        if (message.kind === "reply") return <Reply key={message.id} turn={message.turn} />;
        return (
          <Failure
            key={message.id}
            failure={message.failure}
            at={message.at}
            busy={busy}
            onRetry={() => onRetry(message.messageId)}
          />
        );
      })}
    </>
  );
}
