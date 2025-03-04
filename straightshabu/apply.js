document.addEventListener("DOMContentLoaded", function () {
    let applicationId = null;
    let currentStep = 1;
    const totalSteps = document.querySelectorAll(".form-step").length;
    const form = document.getElementById("application-form");
    const stepIndicator = document.querySelectorAll(".step");
    const messageContainer = document.createElement("div");

    messageContainer.classList.add("message-container");
    form.parentNode.insertBefore(messageContainer, form);

    function showStep(step) {
        document.querySelectorAll(".form-step").forEach((formStep, index) => {
            formStep.classList.toggle("active", index + 1 === step);
        });
        updateStepIndicator(step);
    }

    function updateStepIndicator(step) {
        stepIndicator.forEach((indicator, index) => {
            indicator.classList.toggle("active", index + 1 === step);
        });
    }

    function showMessage(message, type = "success") {
        const messageContainer = document.getElementById("message-container");
        messageContainer.textContent = message;
        messageContainer.className = `message-container ${type}`;
        messageContainer.style.display = "block";

        setTimeout(() => {
            messageContainer.style.display = "none";
        }, 3000);
    }

    function validateAge(dobString) {
        let dob = new Date(dobString);
        let today = new Date();
        let age = today.getFullYear() - dob.getFullYear();

        if (
            today.getMonth() < dob.getMonth() ||
            (today.getMonth() === dob.getMonth() && today.getDate() < dob.getDate())
        ) {
            age--;
        }

        return age >= 21;
    }

    window.submitStep = async function (step) {
        let formElement = document.getElementById("application-form");
        let formData = new FormData(formElement);
        let jsonData = {};

        formData.forEach((value, key) => {
            jsonData[key] = value;
        });

        if (applicationId) {
            jsonData["application_id"] = applicationId;
        }

        if (step === 1) {
            let dobInput = jsonData["date_of_birth"];
            if (!validateAge(dobInput)) {
                showMessage("You must be at least 21 years old to apply.", "error");
                return;
            }
        }

        console.log(`Submitting Step ${step}:`, jsonData);

        try {
            const response = await fetch(`/employee/apply/step/${step}/`, {
                method: "POST",
                body: JSON.stringify(jsonData),
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
                }
            });

            const data = await response.json();
            console.log("Response:", data);

            if (data.success) {
                if (step === 1 && data.application_id) {
                    applicationId = data.application_id;
                    console.log("Stored Application ID:", applicationId);
                }
                showMessage("Step " + step + " completed successfully!", "success");
                setTimeout(() => {
                    nextStep(step + 1);
                }, 1000);
            } else {
                showMessage("Error: " + data.message, "error");
            }
        } catch (error) {
            console.error("Error:", error);
            showMessage("An error occurred. Please try again.", "error");
        }
    };

    window.nextStep = function (step) {
        console.log("Moving to Step:", step);
        let currentStepElement = document.querySelector(".form-step.active");
        let nextStepElement = document.getElementById("step" + step);

        if (currentStepElement && nextStepElement) {
            currentStepElement.classList.remove("active");
            nextStepElement.classList.add("active");
            currentStep = step;
        } else {
            console.error("Step elements not found!");
        }
        updateStepIndicator(step);
    };

    window.prevStep = function (prevStep) {
        if (prevStep >= 1) {
            currentStep = prevStep;
            showStep(currentStep);
        }
    };

    window.submitFinalStep = async function () {
        let form = document.getElementById("application-form");
    
        if (!applicationId) {
            showMessage("Error: Application ID is missing!", "error");
            console.error("Application ID is missing before final submit!");
            return;
        }
    
        let formData = new FormData(form);
        formData.append("application_id", applicationId);
    
        console.log("Submitting Final Step with Application ID:", applicationId);
    
        try {
            const response = await fetch(`/employee/apply/step/4/`, {
                method: "POST",
                headers: { "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value },
                body: formData
            });
    
            const data = await response.json();
            console.log("Final Step Response:", data);
    
            if (data.success) {
                showMessage("Application submitted successfully!", "success");
                setTimeout(() => { 
                    window.location.href = "/employee/application-success/"; 
                }, 2000);
            } else {
                showMessage("Error: " + data.message, "error");
            }
        } catch (error) {
            console.error("Error:", error);
            showMessage("Something went wrong. Please try again.", "error");
        }
    };
    
    showStep(currentStep);
});
