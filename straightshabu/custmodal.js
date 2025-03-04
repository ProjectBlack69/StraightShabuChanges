function openModal(modalId) {
    const modal = document.getElementById(modalId);
    modal.style.display = "block"; // Show the modal
  }
  
  function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    modal.style.display = "none"; // Hide the modal
  }
  
  function toggleModal(closeId, openId) {
    closeModal(closeId);
    openModal(openId);
  }
  
  // Close modal when clicking outside of it
  window.onclick = function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
      if (event.target === modal) {
        modal.style.display = "none";
      }
    });
  };

// Close modal if the user clicks outside of modal content
window.onclick = function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target === modal) {
            closeModal(modal.id);
        }
    });
};

function updateNavbar() {
    // Define button elements for easier adjustments
    const loginBtn = document.getElementById("loginbtn");
    const signupBtn = document.getElementById("signupbtn");
    const profileBtn = document.getElementById("profile-btn");
    const logoutBtn = document.getElementById("logout-btn");
    const notificationDropdown = document.getElementById("notification-dropdown");

    fetch('/customer/get-login-status/')
        .then(response => response.json())
        .then(data => {
            const isLoggedIn = data.is_logged_in;
            const userRole = data.role;

            // Show/hide elements based on login status and user role
            if (isLoggedIn && userRole === 'customer') {
                loginBtn.style.display = "none";
                signupBtn.style.display = "none";
                profileBtn.style.display = "block";
                logoutBtn.style.display = "block";
                if (notificationDropdown) {
                    notificationDropdown.style.display = "block"; // Show notifications
                }
            } else {
                loginBtn.style.display = "block";
                signupBtn.style.display = "block";
                profileBtn.style.display = "none";
                logoutBtn.style.display = "none";
                if (notificationDropdown) {
                    notificationDropdown.style.display = "none"; // Hide notifications
                }
            }
        })
        .catch(error => console.error('Error fetching login status:', error));
}

document.addEventListener('DOMContentLoaded', function () {
    const dropdown = document.getElementById("notificationDropdown");
    const dropdownButton = document.querySelector('.dropbtn');

    // Toggle the dropdown when the button is clicked
    dropdownButton.addEventListener('click', function (event) {
        event.stopPropagation(); // Prevent the click from propagating to the window event
        dropdown.classList.toggle("show");
    });

    // Close the dropdown if clicking outside of it
    window.addEventListener('click', function (event) {
        if (!dropdown.contains(event.target) && !dropdownButton.contains(event.target)) {
            dropdown.classList.remove("show");
        }
    });
});

function markNotificationsRead() {
    fetch('/customer/mark-all-notifications-read/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': '{{ csrf_token }}',
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update unread count badge
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                badge.textContent = data.unread_count;
                if (data.unread_count === 0) {
                    badge.style.display = 'none';
                }
            }

            // Update dropdown content
            const dropdownContent = document.getElementById('notificationDropdown');
            if (data.unread_count === 0) {
                dropdownContent.innerHTML = `
                    <p>No new notifications.</p>
                    <div class="actions">
                        <a href="/customer/notifications/" class="view-all">View All</a>
                    </div>
                `;
            }
        } else {
            console.error('Error:', data.message);
        }
    })
    .catch(error => {
        console.error('Fetch error:', error);
    });
}

// Ensure the navbar updates when the page loads
document.addEventListener("DOMContentLoaded", updateNavbar);

//  Function to show the success modal and reload the page after closing
function showSuccessModal(message, reloadAfterClose = false) {
    const successModal = document.getElementById('authsuccessModal');
    const successMessage = document.getElementById('successMessage');

    if (successModal && successMessage) {
        successMessage.textContent = message;
        successModal.style.display = 'block';

        // Automatically close modal and reload page after 2.5s
        setTimeout(() => {
            closeModal('authsuccessModal');
            if (reloadAfterClose) {
                setTimeout(() => window.location.reload(), 500);
            }
        }, 2500);
    }
}

//  Function to close the modal
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

//  Login Form Submission
document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function (event) {
            event.preventDefault();
            const loginData = new FormData(loginForm);
            const data = {};
            loginData.forEach((value, key) => { data[key] = value; });

            fetch("/customer/login/", {
                method: "POST",
                body: JSON.stringify(data),
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showSuccessModal("Logged in successfully!", true);
                } else {
                    document.getElementById('loginMessage').textContent = data.message;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('loginMessage').textContent = "An error occurred. Please try again.";
            });
        });
    }
});

// Logout Function with Redirect to /customer/
function logout() {
    fetch('/customer/logout/', {
        method: 'POST',
        headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showSuccessModal("Logged out successfully!", false);

            // Delay redirect until after the modal closes (2.5s)
            setTimeout(() => {
                window.location.href = '/customer/';
            }, 2500);
        } else {
            alert('Logout failed. Please try again.');
        }
    })
    .catch(error => console.error('Error during logout:', error));
}

// Signup Form Submission
document.addEventListener('DOMContentLoaded', function () {
    const signupForm = document.getElementById('signupForm');
    const signupMessage = document.getElementById('signupMessage');

    if (signupForm) {
        signupForm.addEventListener('submit', function (event) {
            event.preventDefault();

            // Clear previous messages
            signupMessage.textContent = "";
            document.querySelectorAll(".error-message").forEach(el => el.remove());

            // Frontend validation: Check if passwords match
            const password1 = signupForm.querySelector('[name="password1"]').value;
            const password2 = signupForm.querySelector('[name="password2"]').value;

            if (password1 !== password2) {
                showError(signupForm.querySelector('[name="password2"]'), "Passwords do not match.");
                return;
            }

            // Prepare form data
            const signupData = new FormData(signupForm);

            fetch("/customer/signup/", {
                method: "POST",
                body: signupData,
                headers: {
                    "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
                    "Accept": "application/json"
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showSuccessModal("Signed up successfully!", true);
                    signupForm.reset(); // Clear form on success
                } else {
                    // Show general message
                    signupMessage.innerHTML = `<p style="color: #ff6060;">${data.message || "Signup failed. Please try again."}</p>`;
                    
                    // Display specific field errors
                    for (let field in data.errors) {
                        let inputField = signupForm.querySelector(`[name="${field}"]`);
                        if (inputField) {
                            showError(inputField, data.errors[field][0].message);
                        }
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                signupMessage.innerHTML = `<p style="color: #ff6060;">An error occurred. Please try again.</p>`;
            });
        });
    }

    // Function to display error message below input fields
    function showError(inputElement, message) {
        let errorDiv = document.createElement("div");
        errorDiv.className = "error-message";
        errorDiv.style.color = "red";
        errorDiv.style.fontSize = "14px";
        errorDiv.style.marginTop = "5px";
        errorDiv.innerText = message;
        inputElement.insertAdjacentElement("afterend", errorDiv);
    }
});
