/**
 * Custom hook for consistent error handling with toast notifications.
 * Eliminates duplicate error handling code across components.
 */

import { useToast } from "@/hooks/use-toast";
import { AxiosError } from "axios";
import { useCallback } from "react";

interface ErrorToastOptions {
    title?: string;
    fallbackMessage?: string;
}

/**
 * Extract a user-friendly error message from various error types
 */
export function extractErrorMessage(error: unknown, fallback = "Unknown error"): string {
    if (error instanceof AxiosError) {
        // Handle Axios errors - prefer detail from API response
        return error.response?.data?.detail ?? error.message ?? fallback;
    }
    if (error instanceof Error) {
        return error.message;
    }
    if (typeof error === "string") {
        return error;
    }
    return fallback;
}

/**
 * Hook that provides error-to-toast functionality
 */
export function useErrorToast() {
    const { toast } = useToast();

    /**
     * Show an error toast with consistent formatting
     */
    const showError = useCallback(
        (error: unknown, options: ErrorToastOptions = {}) => {
            const { title = "Error", fallbackMessage = "An unexpected error occurred" } = options;
            const message = extractErrorMessage(error, fallbackMessage);

            toast({
                variant: "destructive",
                title,
                description: message,
            });
        },
        [toast]
    );

    /**
     * Create an onError handler for react-query mutations
     */
    const createErrorHandler = useCallback(
        (title: string, fallbackMessage?: string) => {
            return (error: unknown) => {
                showError(error, { title, fallbackMessage });
            };
        },
        [showError]
    );

    return {
        showError,
        createErrorHandler,
        extractErrorMessage,
    };
}
