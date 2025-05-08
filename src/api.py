from dataclasses import dataclass 
from typing import Any, List, Optional

from pydantic import JsonValue
from requests import Request, Response, Session

# 自定義例外錯誤
class CaptchaException(Exception):
    pass

class LoginException(Exception):
    pass

class NotFoundException(Exception):
    pass

class UnAuthorizedException(Exception):
    pass

@dataclass
class APIClient:
    base_url: str
    session: Session = Session()
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

    def request(
        self,        
        url: str,        
        token: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,        
    ) -> Response:
        response = self.session.send(
            Request(
                method="POST" if data else "GET",
                url=url,
                json=data,
                headers={
                    "User-Agent": self.user_agent,
                    "Authorization": f"Bearer {token}" if token else "",
                },
                cookies=self.session.cookies,
            ).prepare()
        )
        
        match response.status_code:
            case 401:
                raise UnAuthorizedException(
                    f"You are not authorized to access the resource with URL: '{url}'. Please try again with the correct credentials."
                )
            case 403 if response.json().get("blockScript"):
                raise CaptchaException(
                    f"Request to '{url}' with user agent '{self.user_agent}' was blocked, and the API requests you to solve a captcha. Please try logging in again with a different user agent."
                )
            case 404:
                raise NotFoundException(
                    f"The requested resource with URL: '{url}' was not found. Please check the URL and try again."
                )
            
        return response
    
    # 登入取得 JWT
    def login(self, username: str, password: str) -> str:
        url = f"{self.base_url}/login"
        response = self.request(url, data={"login": username, "password": password})

        #check if the response body is empty or invalid
        try:
            response_json = response.json()
        except ValueError:
            raise LoginException(
                f"Failed to parse login response as JSON. Response content: {response.text}"
            )
        
        # Check if the response indicates a failure.
        if "failure" in response_json:
            raise LoginException(
                f"Failed to log in with your current credentials. Response: {response_json.get('message', 'Unknown error')}"
            )

        # Ensure the JWT token is present in the response headers.
        if "jwt" not in response.headers:
            raise LoginException(
                "Login succeeded, but no JWT token was found in the response headers."
            )
        
        return response.headers["jwt"]
    
    def fetch_data(self, username: str, token: str) -> tuple[JsonValue, JsonValue]:
        user_url = f"{self.base_url}/users/{username}"
        user_response_data = self.request(user_url, token).json()
        
        summary_url = f"{self.base_url}/2017-06-30/users/{user_response_data['id']}/xp_summaries?startDate=1970-01-01"
        summary_response_data = self.request(summary_url, token).json()

        return (user_response_data, summary_response_data)