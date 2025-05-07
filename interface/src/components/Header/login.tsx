import { useGoogleLogin, CodeResponse } from '@react-oauth/google';
import { create_current_user } from '@api/sc/agents/googleAuthAgent';
import { ReactComponent as GoogleIcon } from '@assets/icon/google.svg';


const Login: React.FC = () => {
    const login = useGoogleLogin({
        onSuccess: async (tokenResponse: CodeResponse) => {
            const code = tokenResponse.code;
            console.log('Код авторизации:', code);

            try {
                const response = await fetch('https://oauth2.googleapis.com/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        code,
                        client_id: String(process.env.GOOGLE_CLIENT_ID),
                        client_secret: String(process.env.CLIENT_SECRET),
                        redirect_uri: 'postmessage',
                        grant_type: 'authorization_code',
                    }),
                });

                if (!response.ok) {
                    throw new Error(`Ошибка обмена кода: ${response.statusText}`);
                }

                const tokenData = await response.json();
                console.log('Данные токенов:', tokenData);

                const creds = {
                    token: tokenData.access_token,
                    refresh_token: tokenData.refresh_token,
                    token_uri: 'https://oauth2.googleapis.com/token',
                    client_id: String(process.env.GOOGLE_CLIENT_ID),
                    client_secret: String(process.env.CLIENT_SECRET),
                    scopes: ['https://www.googleapis.com/auth/calendar.events'],
                    expiry: new Date(Date.now() + tokenData.expires_in * 1000).toISOString(),
                };

                const credsJson = JSON.stringify(creds, null, 2);
                console.log('Учетные данные:', credsJson);

                await create_current_user(credsJson);
            } catch (error) {
                console.error('Ошибка при получении токенов:', error);
            }
        },
        onError: (error) => {
            console.error('Ошибка входа:', error);
        },
        flow: 'auth-code',
        scope: 'https://www.googleapis.com/auth/calendar.events',
    });

    return (
        <div>
            <button className="google-login-button" onClick={() => login()}>
                <GoogleIcon />
                Войти через Google
            </button>
        </div>
    );
};

export default Login;
