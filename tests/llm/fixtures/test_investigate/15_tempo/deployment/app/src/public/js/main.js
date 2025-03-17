// Create a unique trace ID for this user session
function generateTraceId() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// Set up tracing
const traceId = generateTraceId();
const spanId = generateTraceId().substring(0, 16);

document.addEventListener("DOMContentLoaded", () => {
  // Fetch the page with the trace context
  console.log(`Frontend trace started with ID: ${traceId}`);

  const checkoutForm = document.getElementById("checkoutForm");
  const resultDiv = document.getElementById("result");

  checkoutForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(checkoutForm);
    const checkoutData = Object.fromEntries(formData.entries());

    try {
      // Include the trace context in the headers
      const response = await fetch("/backend/api/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // traceparent: `00-${traceId}-${spanId}-01`,
        },
        body: JSON.stringify(checkoutData),
      });

      const result = await response.json();

      resultDiv.textContent = `Checkout ${result.success ? "completed" : "failed"}: ${result.message}`;
      resultDiv.style.display = "block";
      resultDiv.style.backgroundColor = result.success ? "#d4edda" : "#f8d7da";

      if (result.success) {
        checkoutForm.reset();
      }
    } catch (error) {
      resultDiv.textContent = `Error: ${error.message}`;
      resultDiv.style.display = "block";
      resultDiv.style.backgroundColor = "#f8d7da";
    }
  });
});
