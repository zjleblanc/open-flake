import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { Portal } from "./Portal";

type FieldTooltipProps = {
  ariaLabel: string;
  children: ReactNode;
  /** When true and `children` is a string, render markdown inside the tooltip. */
  rich?: boolean;
};

type TooltipPosition = {
  top: number;
  left: number;
  maxWidth: number;
};

let activeClose: (() => void) | null = null;

function claimExclusive(close: () => void) {
  if (activeClose && activeClose !== close) {
    activeClose();
  }
  activeClose = close;
}

function releaseExclusive(close: () => void) {
  if (activeClose === close) {
    activeClose = null;
  }
}

function renderContent(children: ReactNode, rich?: boolean): ReactNode {
  if (children == null || children === false) return null;
  if (rich && typeof children === "string") {
    return <MarkdownRenderer content={children} className="field-tooltip-rich" />;
  }
  if (typeof children === "string") {
    return <p className="field-tooltip-plain">{children}</p>;
  }
  return children;
}

export function FieldTooltip({ ariaLabel, children, rich }: FieldTooltipProps) {
  const tooltipId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<number | null>(null);
  const closeRef = useRef<() => void>(() => undefined);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<TooltipPosition | null>(null);

  const clearCloseTimer = useCallback(() => {
    if (closeTimerRef.current != null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);

  const close = useCallback(() => {
    clearCloseTimer();
    setOpen(false);
    setPosition(null);
    releaseExclusive(closeRef.current);
  }, [clearCloseTimer]);

  closeRef.current = close;

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const maxWidth = Math.min(22 * 16, window.innerWidth * 0.7);
    const gap = 8;
    let left = rect.left + rect.width / 2;
    left = Math.max(maxWidth / 2 + 8, Math.min(left, window.innerWidth - maxWidth / 2 - 8));
    setPosition({
      top: rect.top - gap,
      left,
      maxWidth,
    });
  }, []);

  const openTooltip = useCallback(() => {
    clearCloseTimer();
    claimExclusive(closeRef.current);
    updatePosition();
    setOpen(true);
  }, [clearCloseTimer, updatePosition]);

  const scheduleClose = useCallback(() => {
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      closeRef.current();
    }, 120);
  }, [clearCloseTimer]);

  useEffect(() => {
    if (!open) return;

    const onScroll = (event: Event) => {
      const target = event.target;
      if (target instanceof Node && tooltipRef.current?.contains(target)) {
        return;
      }
      closeRef.current();
    };
    const onResize = () => closeRef.current();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
    };

    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(
    () => () => {
      clearCloseTimer();
      releaseExclusive(closeRef.current);
    },
    [clearCloseTimer]
  );

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
  }, [open, updatePosition, children]);

  return (
    <span className="field-tooltip-wrap">
      <button
        ref={triggerRef}
        type="button"
        className="field-tooltip-trigger"
        aria-label={ariaLabel}
        aria-describedby={open ? tooltipId : undefined}
        aria-expanded={open}
        onMouseEnter={openTooltip}
        onMouseLeave={scheduleClose}
        onFocus={openTooltip}
        onBlur={scheduleClose}
      >
        ?
      </button>
      {open && position ? (
        <Portal>
          <div
            ref={tooltipRef}
            id={tooltipId}
            role="tooltip"
            className="field-tooltip"
            style={{
              top: position.top,
              left: position.left,
              maxWidth: position.maxWidth,
            }}
            onMouseEnter={clearCloseTimer}
            onMouseLeave={scheduleClose}
          >
            {renderContent(children, rich)}
          </div>
        </Portal>
      ) : null}
    </span>
  );
}
