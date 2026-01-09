import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface SmartDropdownProps {
    trigger: React.ReactNode;
    children: React.ReactNode;
    isOpen: boolean;
    onOpenChange: (isOpen: boolean) => void;
    className?: string; // Class for the dropdown menu container
}

export function SmartDropdown({ trigger, children, isOpen, onOpenChange, className = "" }: SmartDropdownProps) {
    const triggerRef = useRef<HTMLDivElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const [position, setPosition] = useState<'bottom' | 'top'>('bottom');
    const [coords, setCoords] = useState<{ top: number; left: number; width: number }>({ top: 0, left: 0, width: 0 });

    useEffect(() => {
        if (!isOpen || !triggerRef.current) return;

        const updatePosition = () => {
            if (!triggerRef.current) return;

            const triggerRect = triggerRef.current.getBoundingClientRect();
            const spaceBelow = window.innerHeight - triggerRect.bottom;
            const menuHeight = menuRef.current?.offsetHeight || 100; // Estimate if not rendered yet, or use a min height

            // If space below is less than estimated menu height (plus some buffer), and there is more space above, open upwards
            // Buffer of 10px
            const shouldOpenUp = spaceBelow < menuHeight + 10 && triggerRect.top > spaceBelow;

            setPosition(shouldOpenUp ? 'top' : 'bottom');

            setCoords({
                top: shouldOpenUp ? triggerRect.top + window.scrollY : triggerRect.bottom + window.scrollY,
                left: triggerRect.left + window.scrollX, // Aligned to left by default, but we might want right alignment
                width: triggerRect.width
            });
        };

        // Initial calculation
        // We might need a small delay or double render to get the exact menu height if it's dynamic
        // For now, we'll try to calculate immediately.
        updatePosition();

        window.addEventListener('scroll', updatePosition, true);
        window.addEventListener('resize', updatePosition);

        return () => {
            window.removeEventListener('scroll', updatePosition, true);
            window.removeEventListener('resize', updatePosition);
        };
    }, [isOpen]);

    // Handle clicking outside
    useEffect(() => {
        if (!isOpen) return;

        const handleClickOutside = (event: MouseEvent) => {
            if (
                menuRef.current &&
                !menuRef.current.contains(event.target as Node) &&
                triggerRef.current &&
                !triggerRef.current.contains(event.target as Node)
            ) {
                onOpenChange(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => { document.removeEventListener('mousedown', handleClickOutside); };
    }, [isOpen, onOpenChange]);


    return (
        <>
            <div ref={triggerRef} onClick={() => { onOpenChange(!isOpen); }} className="inline-block">
                {trigger}
            </div>
            {isOpen && createPortal(
                <div
                    ref={menuRef}
                    style={{
                        position: 'absolute',
                        top: position === 'bottom' ? coords.top : 'auto',
                        bottom: position === 'top' ? (window.innerHeight - coords.top + window.scrollY) : 'auto',
                        // For right alignment relative to trigger:
                        left: coords.left + coords.width,
                        transform: 'translateX(-100%)', // Move it back to align right edge with trigger right edge
                        zIndex: 9999, // Ensure it's on top
                    }}
                    className={`min-w-[120px] ${position === 'top' ? 'mb-1' : 'mt-1'} ${className}`}
                >
                    {children}
                </div>,
                document.body
            )}
        </>
    );
}
