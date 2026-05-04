/**
 * Developer Utilities
 */

export function autofillForTesting() {
    console.log("🛠️ Autofilling for testing...");
    
    // Profile
    const userName = document.getElementById('user-name');
    const userCompany = document.getElementById('user-company');
    const userRole = document.getElementById('user-role');
    const userResume = document.getElementById('user-resume');
    
    if (userName) userName.value = "John Doe";
    if (userCompany) userCompany.value = "Google";
    if (userRole) userRole.value = "Senior Software Engineer";
    if (userResume) userResume.value = "Experienced engineer with focus on AI and distributed systems.";
    
    // Focus
    const focusCheckboxes = document.querySelectorAll('input[name="focus"]');
    if (focusCheckboxes.length > 0) {
        focusCheckboxes[0].checked = true;
        focusCheckboxes[2].checked = true;
    }
}
