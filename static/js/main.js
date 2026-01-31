document.addEventListener("DOMContentLoaded", function () {
  const queryInput = document.getElementById("query-input");
  const submitButton = document.getElementById("submit-query");
  const visualizationToggle = document.getElementById("visualization-toggle");
  const modeDirect = document.getElementById("mode-direct");
  const modeDeep = document.getElementById("mode-deep");
  const loadingElement = document.getElementById("loading");
  const errorElement = document.getElementById("error");
  const resultsElement = document.getElementById("results");
  const sqlDisplay = document.getElementById("sql-display");
  const dataDisplay = document.getElementById("data-display");
  const visualizationDisplay = document.getElementById("visualization");

  // Handle form submission
  submitButton.addEventListener("click", async function () {
    const query = queryInput.value.trim();
    if (!query) {
      showError("Please enter a query");
      return;
    }

    // Show loading state
    showLoading();
    hideError();
    clearResults();

    try {
      const response = await fetch("/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query,
          visualization: visualizationToggle.checked,
          mode: modeDeep && modeDeep.checked ? "deep" : "direct",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "An error occurred");
      }

      // Display results
      if (data && data.mode === "deep" && Array.isArray(data.subqueries)) {
        displayDeepResults(data);
      } else {
        displayResults(data);
      }

      // If visualization is requested, generate it
      if (visualizationToggle.checked) {
        generateVisualization(data);
      }
    } catch (error) {
      showError(error.message);
    } finally {
      hideLoading();
    }
  });

  function showLoading() {
    loadingElement.style.display = "block";
    resultsElement.style.display = "none";
  }

  function hideLoading() {
    loadingElement.style.display = "none";
    resultsElement.style.display = "block";
  }

  function showError(message) {
    errorElement.textContent = message;
    errorElement.style.display = "block";
  }

  function hideError() {
    errorElement.style.display = "none";
  }

  function clearResults() {
    sqlDisplay.innerHTML = "";
    dataDisplay.innerHTML = "";
    visualizationDisplay.innerHTML = "";
  }

  function displayResults(data) {
    // Display SQL query
    sqlDisplay.textContent = data.sql;

    // Display data in a table
    if (data.data && data.data.rows && data.data.rows.length > 0) {
      const table = document.createElement("table");
      table.className = "results-table";

      // Create header row
      const thead = document.createElement("thead");
      const headerRow = document.createElement("tr");
      data.data.headers.forEach((header) => {
        const th = document.createElement("th");
        th.textContent = header;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      // Create data rows
      const tbody = document.createElement("tbody");
      data.data.rows.forEach((row) => {
        const tr = document.createElement("tr");
        row.forEach((cell) => {
          const td = document.createElement("td");
          td.textContent = cell;
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);

      dataDisplay.innerHTML = "";
      dataDisplay.appendChild(table);
    } else {
      dataDisplay.innerHTML = "<p>No results found</p>";
    }
  }

  function displayDeepResults(payload) {
    sqlDisplay.innerHTML = "";
    dataDisplay.innerHTML = "";

    const title = document.createElement("h3");
    title.textContent = "Deep analysis results";
    dataDisplay.appendChild(title);

    payload.subqueries.forEach((sq) => {
      const section = document.createElement("div");
      section.style.margin = "16px 0";

      const h = document.createElement("div");
      h.style.fontWeight = "600";
      h.style.marginBottom = "6px";
      h.textContent = `${sq.id || ""} • ${sq.question || ""}`;
      section.appendChild(h);

      const pre = document.createElement("pre");
      pre.style.background = "#f6f8fa";
      pre.style.padding = "8px";
      pre.style.borderRadius = "6px";
      pre.style.fontFamily = "Fira Code, monospace";
      pre.textContent = sq.sql || "";
      section.appendChild(pre);

      const exec = sq.execution || {};
      if (
        exec.success &&
        exec.data &&
        exec.data.rows &&
        exec.data.rows.length > 0
      ) {
        const table = document.createElement("table");
        table.className = "results-table";

        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        (exec.data.headers || []).forEach((header) => {
          const th = document.createElement("th");
          th.textContent = header;
          headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        (exec.data.rows || []).forEach((row) => {
          const tr = document.createElement("tr");
          row.forEach((cell) => {
            const td = document.createElement("td");
            td.textContent = cell;
            tr.appendChild(td);
          });
          tbody.appendChild(tr);
        });
        table.appendChild(tbody);

        section.appendChild(table);
      } else {
        const p = document.createElement("p");
        p.textContent = exec.error ? `Error: ${exec.error}` : "No results";
        section.appendChild(p);
      }

      dataDisplay.appendChild(section);
    });
  }

  function generateVisualization(data) {
    console.log("Starting visualization generation...");
    const query = queryInput.value;
    console.log("Query:", query);

    fetch("/visualize", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: query,
        resultData: data.data,
      }),
    })
      .then((response) => {
        console.log("Received response from server");
        return response.json();
      })
      .then((data) => {
        console.log("Server response data:", data);

        if (data.error) {
          console.error("Error from server:", data.error);
          showError("Error generating visualization: " + data.error);
          return;
        }

        // Clear any existing content
        visualizationDisplay.innerHTML = "";
        console.log("Cleared existing content");

        // Create and add the image
        const img = document.createElement("img");
        console.log("Created image element");

        // Add timestamp to prevent caching
        const timestamp = new Date().getTime();
        img.src = `/static/visualization.png?t=${timestamp}`;
        img.alt = "Visualization";
        img.style.width = "100%";
        img.style.maxWidth = "800px";
        img.style.margin = "20px auto";
        img.style.display = "block";

        // Add error handling for image loading
        img.onerror = function () {
          console.error("Failed to load visualization image");
          visualizationDisplay.innerHTML = "<p>Error loading visualization</p>";
        };

        img.onload = function () {
          console.log("Image loaded successfully");
          // Force a reflow to ensure the image is displayed
          img.style.display = "none";
          img.offsetHeight; // Trigger reflow
          img.style.display = "block";
        };

        visualizationDisplay.appendChild(img);
        console.log("Image appended to div");
      })
      .catch((error) => {
        console.error("Error in visualization process:", error);
        showError("Error generating visualization");
      });
  }
});
