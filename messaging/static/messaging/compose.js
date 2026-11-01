function composeToken(form) {
    var input = form.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
}

function refreshPreview(form) {
    var schedule = form.querySelector("[data-compose-schedule]");
    var template = form.querySelector("[data-compose-template]");
    var subject = form.querySelector("[data-preview-subject]");
    var body = form.querySelector("[data-preview-body]");
    var error = form.querySelector("[data-preview-error]");
    if (!schedule || !template || !schedule.value || !template.value) {
        if (subject) subject.value = "";
        if (body) body.value = "";
        return;
    }
    var params = new URLSearchParams();
    params.set("schedule", schedule.value);
    params.set("template", template.value);
    fetch(form.dataset.previewUrl, {
        method: "POST",
        headers: {
            "X-CSRFToken": composeToken(form),
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body: params.toString(),
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        })
        .then(function (result) {
            if (!result.ok) {
                error.hidden = false;
                error.textContent = result.data.error || "Could not preview this message.";
                return;
            }
            error.hidden = true;
            subject.value = result.data.subject;
            body.value = result.data.body;
            var list = form.querySelector("[data-preview-recipients]");
            if (list && result.data.recipients) {
                list.replaceChildren();
                result.data.recipients.forEach(function (label) {
                    var item = document.createElement("li");
                    item.textContent = label;
                    list.appendChild(item);
                });
                if (!result.data.recipients.length) {
                    var empty = document.createElement("li");
                    empty.textContent = "No active members.";
                    list.appendChild(empty);
                }
            }
        })
        .catch(function () {
            error.hidden = false;
            error.textContent = "Could not preview this message.";
        });
}

document.addEventListener("change", function (event) {
    if (!event.target.matches("[data-compose-schedule], [data-compose-template]")) {
        return;
    }
    var form = event.target.closest("form");
    if (form) refreshPreview(form);
});

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-compose-form]").forEach(refreshPreview);
});

document.addEventListener("click", function (event) {
    var openButton = event.target.closest("#send-schedule");
    if (openButton) {
        var dialog = document.getElementById("send-schedule-dialog");
        fetch(openButton.dataset.composeUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(function (response) {
                if (!response.ok) throw new Error("Could not open the message.");
                return response.text();
            })
            .then(function (html) {
                dialog.innerHTML = html;
                dialog.showModal();
                var form = dialog.querySelector("[data-compose-form]");
                if (form) refreshPreview(form);
            })
            .catch(function (error) {
                dialog.innerHTML = "<p>" + error.message + "</p>";
                dialog.showModal();
            });
        return;
    }
    if (event.target.matches("[data-compose-cancel]")) {
        var cancelDialog = event.target.closest("dialog");
        if (cancelDialog) cancelDialog.close();
    }
});

document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || !event.target.matches("[data-test-email]")) {
        return;
    }
    var form = event.target.closest("form");
    var button = form && form.querySelector("[data-send-test]");
    if (!button) {
        return;
    }
    event.preventDefault();
    button.click();
});

document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches("[data-compose-form]") || !form.closest("dialog")) {
        return;
    }
    event.preventDefault();
    var error = form.querySelector("[data-preview-error]");
    var action = event.submitter && event.submitter.formAction
        ? event.submitter.formAction
        : form.action;
    fetch(action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "XMLHttpRequest" },
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        })
        .then(function (result) {
            if (!result.ok) {
                error.hidden = false;
                error.textContent = result.data.error || "Send failed.";
                return;
            }
            window.location = result.data.url;
        })
        .catch(function () {
            error.hidden = false;
            error.textContent = "Send failed.";
        });
});
