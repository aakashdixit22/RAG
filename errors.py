

class APIError(Exception):
    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload


class ValidationError(APIError):
    def __init__(self, message, payload=None):
        super().__init__(message, 400, payload)


class AuthError(APIError):
    def __init__(self, message="Authentication required"):
        super().__init__(message, 401)


class NotFoundError(APIError):
    def __init__(self, message="Resource not found"):
        super().__init__(message, 404)


class ConflictError(APIError):
    def __init__(self, message="Resource conflict"):
        super().__init__(message, 409)


class PayloadTooLargeError(APIError):
    def __init__(self, message="Uploaded file exceeds the maximum allowed size"):
        super().__init__(message, 413)


class UnsupportedMediaTypeError(APIError):
    def __init__(self, message="Unsupported file type"):
        super().__init__(message, 415)


def register_error_handlers(app):
    from flask import jsonify

    @app.errorhandler(APIError)
    def handle_api_error(err):
        body = {"error": {"message": err.message}}
        if err.payload:
            body["error"]["details"] = err.payload
        return jsonify(body), err.status_code

    @app.errorhandler(404)
    def handle_404(err):
        return jsonify({"error": {"message": "The requested resource was not found"}}), 404

    @app.errorhandler(405)
    def handle_405(err):
        return jsonify({"error": {"message": "Method not allowed for this endpoint"}}), 405

    @app.errorhandler(413)
    def handle_413(err):
        return jsonify({"error": {"message": "Uploaded file exceeds the maximum allowed size"}}), 413

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled exception")
        return jsonify({"error": {"message": "An internal error occurred. Please try again."}}), 500
