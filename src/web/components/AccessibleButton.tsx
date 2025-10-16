// components/AccessibleButton.tsx
import React from 'react';

import type { LucideIcon } from 'lucide-react';

interface AccessibleButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'success' | 'danger' | 'warning';
    size?: 'sm' | 'md' | 'lg';
    icon?: LucideIcon;
    iconPosition?: 'left' | 'right';
    loading?: boolean;
    loadingText?: string;
    children: React.ReactNode;
}

export const AccessibleButton: React.FC<AccessibleButtonProps> = ({
    variant = 'primary',
    size = 'md',
    icon: Icon,
    iconPosition = 'left',
    loading = false,
    loadingText = 'Loading...',
    disabled,
    children,
    className = '',
    ...props
}) => {
    const baseClasses = 'inline-flex items-center justify-center font-medium rounded transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';

    const variantClasses = {
        primary: 'bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 text-white focus:ring-blue-500',
        secondary: 'bg-gray-500 hover:bg-gray-600 disabled:bg-gray-300 text-white focus:ring-gray-500',
        success: 'bg-green-500 hover:bg-green-600 disabled:bg-green-300 text-white focus:ring-green-500',
        danger: 'bg-red-500 hover:bg-red-600 disabled:bg-red-300 text-white focus:ring-red-500',
        warning: 'bg-yellow-500 hover:bg-yellow-600 disabled:bg-yellow-300 text-white focus:ring-yellow-500'
    };

    const sizeClasses = {
        sm: 'px-2 py-1 text-sm',
        md: 'px-4 py-2 text-sm',
        lg: 'px-6 py-3 text-base'
    };

    const iconSizeClasses = {
        sm: 'w-3 h-3',
        md: 'w-4 h-4',
        lg: 'w-5 h-5'
    };

    const isDisabled = disabled || loading;

    // Type-safe accessors
    const variantClass = variantClasses[variant];
    const sizeClass = sizeClasses[size];
    const iconSizeClass = iconSizeClasses[size];

    return (
        <button
            className={`${baseClasses} ${variantClass} ${sizeClass} ${className}`}
            disabled={isDisabled}
            aria-busy={loading}
            aria-describedby={loading ? `${props.id}-loading` : undefined}
            {...props}
        >
            {loading && iconPosition === 'left' && (
                <svg
                    className={`${iconSizeClass} mr-2 animate-spin`}
                    fill="none"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                >
                    <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                    />
                    <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                </svg>
            )}

            {!loading && Icon && iconPosition === 'left' && (
                <Icon className={`${iconSizeClass} mr-2`} aria-hidden="true" />
            )}

            <span>
                {loading ? loadingText : children}
            </span>

            {!loading && Icon && iconPosition === 'right' && (
                <Icon className={`${iconSizeClass} ml-2`} aria-hidden="true" />
            )}

            {loading && iconPosition === 'right' && (
                <svg
                    className={`${iconSizeClass} ml-2 animate-spin`}
                    fill="none"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                >
                    <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                    />
                    <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                </svg>
            )}

            {loading && (
                <span id={`${props.id}-loading`} className="sr-only">
                    Loading, please wait
                </span>
            )}
        </button>
    );
};