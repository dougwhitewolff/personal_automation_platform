import { Inngest } from "inngest";

export const inngest = new Inngest({ id: "personal-automation-platform" });

export const plaudCaptureReceived = inngest.createFunction(
  { id: "plaud-capture-received" },
  { event: "plaud/capture.received" },
  async ({ event }) => {
    return { acknowledged: true, data: event.data };
  }
);
