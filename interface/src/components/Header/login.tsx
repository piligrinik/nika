import { useGoogleLogin, GoogleLogin } from '@react-oauth/google';
import React, { useEffect } from 'react';
import { gapi } from 'gapi-script';

// Replace these with your actual credentials from Google Cloud Console
const CLIENT_ID = String(process.env.GOOGLE_CLIENT_ID);
const API_KEY = 'AIzaSyBv8yYgrJ977f6j9qu3kPNhB9voS2CY5ZA';
const DISCOVERY_DOCS = ['https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest'];
const SCOPES = 'https://www.googleapis.com/auth/calendar.events';

const Login: React.FC = () => {


    // Handle successful login
    const onSuccess = (credentialResponse: any) => {
        console.log('Успешный вход:', credentialResponse);
    };

    // Handle login error
    const onError = () => {
        console.error('Ошибка при входе');
    };

    return (
        <div>
            <GoogleLogin 
                onSuccess={onSuccess} 
                onError={onError} 
                theme="filled_black" 
                size="large" 
                text="signin" 
            />
        </div>
    );
};

export default Login;
