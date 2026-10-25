type LogLevel = "debug" | "info" | "warn" | "error";

function emit(level: LogLevel, message: string, extra?: Record<string, unknown>) {
  const payload = {
    timestamp: new Date().toISOString(),
    service: "ai-job-post-frontend",
    level,
    message,
    ...extra,
  };

  if (level === "error") {
    console.error(JSON.stringify(payload));
    return;
  }

  if (level === "warn") {
    console.warn(JSON.stringify(payload));
    return;
  }

  console.info(JSON.stringify(payload));
}

export const logger = {
  debug: (message: string, extra?: Record<string, unknown>) => emit("debug", message, extra),
  info: (message: string, extra?: Record<string, unknown>) => emit("info", message, extra),
  warn: (message: string, extra?: Record<string, unknown>) => emit("warn", message, extra),
  error: (message: string, extra?: Record<string, unknown>) => emit("error", message, extra),
};
