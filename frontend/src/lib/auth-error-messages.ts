type AuthErrorLike = {
  message?: string;
  name?: string;
};

function errorText(error: unknown) {
  if (typeof error !== "object" || error === null) {
    return "";
  }

  const { message, name } = error as AuthErrorLike;
  return `${name ?? ""} ${message ?? ""}`.toLowerCase();
}

function isNetworkError(error: unknown) {
  const text = errorText(error);
  return (
    error instanceof TypeError ||
    text.includes("failed to fetch") ||
    text.includes("network")
  );
}

export function loginErrorMessage(error: unknown) {
  const text = errorText(error);

  if (
    text.includes("invalid login credentials") ||
    text.includes("invalid email or password")
  ) {
    return "The email or password is invalid. Please check both and try again.";
  }

  if (text.includes("email not confirmed")) {
    return "Please confirm your email address before signing in.";
  }

  if (isNetworkError(error)) {
    return "Verity could not reach the sign-in service. Check your connection and try again.";
  }

  return "We could not sign you in. Please try again.";
}

export function signupErrorMessage(error: unknown) {
  const text = errorText(error);

  if (
    text.includes("already registered") ||
    text.includes("already exists") ||
    text.includes("email exists")
  ) {
    return "An account is already registered with this email. Please log in instead.";
  }

  if (isNetworkError(error)) {
    return "Verity could not reach the registration service. Check your connection and try again.";
  }

  return "We could not create your account. Please check your details and try again.";
}

export function signupReturnedExistingAccount(user: {
  identities?: unknown[];
} | null) {
  return Array.isArray(user?.identities) && user.identities.length === 0;
}
