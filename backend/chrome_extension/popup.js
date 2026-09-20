const API_BASE = "http://127.0.0.1:8000";

const captureButton = document.getElementById(
  "captureButton"
);
const askButton = document.getElementById(
  "askButton"
);
const newThreadButton = document.getElementById(
  "newThreadButton"
);

const captureStatus = document.getElementById(
  "captureStatus"
);
const queryInput = document.getElementById(
  "queryInput"
);
const answerOutput = document.getElementById(
  "answerOutput"
);
const routeValue = document.getElementById(
  "routeValue"
);
const verificationValue = document.getElementById(
  "verificationValue"
);


async function captureCurrentPage() {
  captureStatus.textContent = "Capturing...";

  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (!tab || !tab.id) {
      throw new Error(
        "Cannot find active tab."
      );
    }

    const [execution] =
      await chrome.scripting.executeScript({
        target: {
          tabId: tab.id,
        },
        func: () => {
          const text =
            document.body?.innerText || "";

          return {
            title: document.title || null,
            locator: location.href,
            content_text:
              text.slice(0, 12000),
          };
        },
      });

    const page = execution.result;

    const payload = {
      client_event_id:
        crypto.randomUUID(),
      source_type: "web",
      locator: page.locator,
      title: page.title,
      content_text:
        page.content_text,
      event_type: "web_visit",
      observed_at:
        new Date().toISOString(),
      context: {
        tab_id: tab.id,
      },
    };

    const response = await fetch(
      `${API_BASE}/api/v1/capture`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify(
          payload
        ),
      }
    );

    if (!response.ok) {
      throw new Error(
        `Capture failed: ${response.status}`
      );
    }

    const data = await response.json();

    captureStatus.textContent =
      data.duplicate
        ? "Already captured."
        : "Captured successfully.";

  } catch (error) {
    captureStatus.textContent =
      `Error: ${error.message}`;
  }
}


async function askRecallFlow() {
  const message =
    queryInput.value.trim();

  if (!message) {
    answerOutput.textContent =
      "请输入问题。";
    return;
  }

  answerOutput.textContent =
    "RecallFlow is working...";

  routeValue.textContent =
    "Route: -";

  verificationValue.textContent =
    "Verification: -";

  try {
    const stored =
      await chrome.storage.local.get(
        ["thread_id"]
      );

    const payload = {
      thread_id:
        stored.thread_id || null,
      message,
    };

    const response = await fetch(
      `${API_BASE}/api/v1/ask`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify(
          payload
        ),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail
        || `Ask failed: ${response.status}`
      );
    }

    await chrome.storage.local.set({
      thread_id: data.thread_id,
    });

    answerOutput.textContent =
      data.result.answer;

    routeValue.textContent =
      `Route: ${data.result.route}`;

    const verification =
      data.result.verification?.status
      || "none";

    verificationValue.textContent =
      `Verification: ${verification}`;

  } catch (error) {
    answerOutput.textContent =
      `Error: ${error.message}`;
  }
}


async function newThread() {
  await chrome.storage.local.remove(
    ["thread_id"]
  );

  routeValue.textContent =
    "Route: -";

  verificationValue.textContent =
    "Verification: -";

  answerOutput.textContent =
    "New conversation thread created.";

  queryInput.value = "";
}


captureButton.addEventListener(
  "click",
  captureCurrentPage
);

askButton.addEventListener(
  "click",
  askRecallFlow
);

newThreadButton.addEventListener(
  "click",
  newThread
);
