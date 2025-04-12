document.addEventListener("DOMContentLoaded", (event) => {
    var dragSrcEl = null;
    var saveTimer = null;
    var dirty = false;
    var lastValue = "";
    var toastEl = document.getElementById("toast");
    var assignmentFreqMap = new Map();
  
    function hideToast() {
      toastEl.style.opacity = "0.0";
    }
  
    function showToast(message) {
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
        this.toastTimer = null;
      }
      toastEl.innerText = message;
      toastEl.style.opacity = "0.95";
  
      this.toastTimer = setTimeout(function () {
        hideToast();
        this.toastTimer = null;
      }, 1000);
    }

    function collectAssignments() {
          return Array.from(document.querySelectorAll('td.duty-cell'))
            .reduce((obj, cell) => {
              const input = cell.querySelector('input.assignment-input');
              if (input && input.value && cell.dataset.duty) {
                obj[cell.dataset.duty] = input.value;
              }
              return obj;
            }, {})
    }
    // TODO break functions into other files
    async function generateAssignments() {
      // Show skeletons in empty cells
      const emptyCells = document.querySelectorAll('td.duty-cell');
      emptyCells.forEach((cell) => {
        const input = cell.querySelector('input.assignment-input');
        if (input && !input.value) {
          const skeleton = cell.querySelector('.skeleton') || document.createElement('div');
          skeleton.className = 'skeleton visible';
          if (!cell.querySelector('.skeleton')) {
            cell.appendChild(skeleton);
          }
          input.style.display = 'none';
        }
      });

      await fetch(`generate`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(
          collectAssignments()
        ),
      }).then((res) => {
        console.log(res);
        showToast("Done.");
        return res.json().then(data => {
          const assignmentMap = data.assignment_map;
          
          // Hide all skeletons and show inputs
          document.querySelectorAll('.skeleton').forEach(skeleton => {
            skeleton.classList.remove('visible');
            const input = skeleton.parentElement.querySelector('input.assignment-input');
            if (input) {
              input.style.display = '';
            }
          });
          
          // parse results into schedule
          for (const [dutyKey, assigneeName] of Object.entries(assignmentMap)) {
            const dutyCells = document.querySelectorAll(`td.duty-cell[data-duty="${dutyKey}"]`);
            dutyCells.forEach(cell => {
              const input = cell.querySelector('input.assignment-input');
              if (input) {
                input.value = assigneeName;
                input.setAttribute("value", assigneeName);
                input.placeholder = assigneeName;
                input.setAttribute("placeholder", assigneeName);
              }
              else {
                console.log(`No input found for duty cell ${dutyKey}`);
              }
              updateAssignedCount();
            });
          }
          
          showToast("Assignments loaded");
          saveAfterDelay();
        }).catch(error => {
          // Hide skeletons and show inputs on error
          document.querySelectorAll('.skeleton').forEach(skeleton => {
            skeleton.classList.remove('visible');
            const input = skeleton.parentElement.querySelector('input.assignment-input');
            if (input) {
              input.style.display = '';
            }
          });
          console.error("Error parsing assignment data:", error);
          showToast("Error loading assignments");
        });
      });
      showToast("Generating assignments...");
    }
  
    async function clear() {
      if (!confirm("Are you sure you want to clear all assignments in this schedule? This action cannot be undone.")) {
        return;
      }

      await fetch("clear", {
        method: "DELETE",
      }).then((res) => {
        if (res.status === 200 || res.status === 304) {
          setTimeout(() => showToast("Done."), 1000);
          // get all assignments and clear them
          const assignments = document.querySelectorAll("input.assignment-input");
          assignments.forEach((assignment) => {
            assignment.value = "";
            assignment.setAttribute("value", "");
            assignment.placeholder = "";
            assignment.setAttribute("placeholder", "");
          });
        }
      });
      showToast("Clearing assignments...");
    }
  
    function saveAfterDelay() {
      if (this.saveTimer) {
        window.clearTimeout(saveTimer);
        this.saveTimer = null;
      }
  
      this.saveTimer = setTimeout(async function () {
        await fetch("save", {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(collectAssignments()),
      }).then((res) => {
          if (res.status === 204) {
            showToast("Saved");
            updateAssignedCount();
          }
        });
      }, 2000);
      showToast("Saving...");
    }
  
    function toggleAssignmentCountVisibility() {
      const el = document.querySelector(".assignment-map");
      const hidden = el.classList.contains("hidden");
  
      if (hidden) {
        el.classList.remove("hidden");
      } else {
        el.classList.add("hidden");
      }
    }
  
    function updateAssignedCount() {
      assignmentFreqMap.clear();
      var inputs = Array.from($("input.assignment-input"));
  
      inputs.forEach((input) => {
        const value = input.value.replace(/\(\d+\)/, "");
  
        if (assignmentFreqMap.has(value)) {
          assignmentFreqMap.set(value, assignmentFreqMap.get(value) + 1);
        } else {
          assignmentFreqMap.set(value, 1);
        }
      });
  
      var container = document.querySelector("div.assignment-map");
  
      // remove children
      container.replaceChildren();
  
      Array.from(assignmentFreqMap.entries())
        .sort((a, b) => a[0].charCodeAt(0) - b[0].charCodeAt(0))
        .sort((a, b) => b[1] - a[1])
        .forEach((entry) => {
          const div = document.createElement("div");
  
          div.className = "assignment-map-entry";
          div.textContent = `${entry[0]} (${entry[1]})`;
          highlightOnMouseover(div);
          clearHighlightOnMouseout(div);
          container.append(div);
        });
  
      // console.log(assignmentFreqMap);
    }
  
    updateAssignedCount();
  
    function highlightOnMouseover(el) {
      el.addEventListener("mouseenter", (e) => {
        $(el).addClass("search-highlight");
        assignmentInputsByValue(
          el.textContent.replace(/\s\(\d+\)/, ""),
          (input) => $(input).addClass("search-highlight")
        );
      });
    }
  
    function clearHighlightOnMouseout(el) {
      el.addEventListener("mouseleave", (e) => {
        $(el).removeClass("search-highlight");
  
        assignmentInputsByValue(
          el.textContent.replace(/\s\(\d+\)/, ""),
          (input) => $(input).removeClass("search-highlight")
        );
      });
    }
  
    function handleDragStart(e) {
      this.style.opacity = "0.4";
  
      dragSrcEl = this;
  
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/html", this.innerHTML);
    }
  
    function handleDragOver(e) {
      if (e.preventDefault) {
        e.preventDefault();
      }
  
      e.dataTransfer.dropEffect = "move";
  
      return false;
    }
  
    function handleDragEnter(e) {
      this.classList.add("over");
    }
  
    function handleDragLeave(e) {
      this.classList.remove("over");
    }
  
    function handleDrop(e) {
      if (e.stopPropagation) {
        e.stopPropagation(); // stops the browser from redirecting.
      }
  
      if (dragSrcEl != this) {
        dragSrcEl.innerHTML = this.innerHTML;
        this.innerHTML = e.dataTransfer.getData("text/html");
        setupInput(dragSrcEl.querySelector("input"));
        setupInput(this.querySelector("input"));
  
        saveAfterDelay();
      }
  
      return false;
    }
  
    function handleDragEnd(e) {
      this.style.opacity = "1";
  
      items.forEach(function (item) {
        item.classList.remove("over");
      });
    }
  
    function addDragAndDropEventListeners(item) {
      item.addEventListener("dragstart", handleDragStart, false);
      item.addEventListener("dragenter", handleDragEnter, false);
      item.addEventListener("dragover", handleDragOver, false);
      item.addEventListener("dragleave", handleDragLeave, false);
      item.addEventListener("drop", handleDrop, false);
      item.addEventListener("dragend", handleDragEnd, false);
    }
  
    let items = document.querySelectorAll("td.duty-cell");
    items.forEach(function (item) {
      addDragAndDropEventListeners(item);
    });
  
    function addInputListener(input) {
      input.addEventListener("input", function (e) {
        input.setAttribute("value", e.target.value);
      });
    }
  
    function filerOnValueOrPlaceholder(el, value) {
      let placeholder = el.getAttribute("placeholder");
      return (
        (el.value != "" || el.placeholder != "" ) && el.value.trim() == value || (placeholder && placeholder.trim() == value)
      );
    }
  
    function assignmentInputsByValue(val, f) {
      Array.from(
        $(".assignment-input").filter((_, el) =>
          filerOnValueOrPlaceholder(el, val)
        )
      ).forEach((el) => f(el));
    }
  
    function addMouseOverListener(input) {
      input.addEventListener("mouseover", (event) => {
        // find all inputs with same value and change background
        let mouseoverValue = input.getAttribute("value");
  
        assignmentInputsByValue(mouseoverValue, (el) => {
          $(el).addClass("search-highlight");
        });
      });
    }
  
    function addMouseoutListener(input) {
      input.addEventListener("mouseout", (event) => {
        // find all inputs with same value and change background
        let mouseoverValue = input.getAttribute("value").trim();
  
        clearHighlights();
        assignmentInputsByValue(mouseoverValue, (el) => {
          $(el).remove("search-highlight");
        });
      });
    }
  
    function clearHighlights() {
      $(".assignment-input").removeClass("search-highlight");
      $(".assignment-map-entry").removeClass("search-highlight");
    }
  
    function setupInput(input) {
      input.setSelectionRange(-1, -1);
      addInputListener(input);
      addMouseOverListener(input);
      addMouseoutListener(input);
      setupInputEventListeners(input);
    }
  
    let inputs = document.querySelectorAll("input");
    inputs.forEach(function (input) {
      setupInput(input);
    });
  
    document.getElementById("download-pdf").onclick = async function () {
      window.location = "pdf";
    };
  
    // document.getElementById("download-pdf").onclick = pdf;

    document.getElementById("toggle-assignment-count").onclick =
      toggleAssignmentCountVisibility;
  
    document.getElementById("clear-schedule").onclick = clear;

    document.getElementById("generate-assignments").onclick = generateAssignments;

  
    function setupInputEventListeners(input) {
      input.addEventListener("change", function (e) {
        // console.log("change");
        e.target.setAttribute("placeholder", e.target.value);
        dirty = lastValue !== e.target.value;
      });
      input.addEventListener("focus", function (e) {
        // console.log("focus");
        e.target.setAttribute("placeholder", e.target.value);
        lastValue = e.target.value;
        e.target.value = "";
      });
      input.addEventListener("blur", function (e) {
        e.target.value = e.target.getAttribute("placeholder");
        if (dirty) {
          // console.log("dirty blur: {}", e.target.value);
          dirty = false;
          saveAfterDelay();
          clearHighlights();
        }
      });
      input.addEventListener("keyup", function (e) {
        // console.log(`keyup: ${e.key}`);
        if (e.key === "Enter" || e.keyCode === 13) {
          // autocomplete using first option in list
          autocompleteDatalist(input);
          // activate blur to save
          document.activeElement.blur();
          // reset highlights
          clearHighlights();
        }
  
        if (!e.key) {
          e.target.blur();
        }
      });
    }
  
    function autocompleteDatalist(input) {
      const datalist = input.getAttribute("list");
      const options = Array.from(
        document.querySelector(`datalist#${datalist}`).options
      ).map(function (el) {
        return el.value;
      });
      var relevantOptions = options.filter(function (option) {
        return option.toLowerCase().includes(input.value.toLowerCase());
      });
      if (relevantOptions.length > 0) {
        input.placeholder = relevantOptions.shift();
        input.innerHTML = input.placeholder;
        input.setAttribute("value", input.placeholder);
      }
    }
  });
  