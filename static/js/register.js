document.getElementById('register-form').addEventListener('submit', function(event) {

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    // Perform registration logic here, e.g., send a request to the server
    console.log('Registering with', username, password);

});