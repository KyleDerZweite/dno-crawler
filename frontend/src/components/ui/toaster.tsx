import { Toast } from "@/components/ui/toast";
import { useToast } from "@/hooks/use-toast";

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="fixed bottom-0 right-0 z-[100] flex flex-col gap-2 p-4 max-w-[420px] w-full pointer-events-none">
      {toasts.map(({ id, title, description, variant }) => (
        <Toast
          key={id}
          id={id}
          title={title}
          description={description}
          variant={variant}
          onClose={() => { dismiss(id); }}
          className="pointer-events-auto animate-in slide-in-from-bottom-5"
        />
      ))}
    </div>
  );
}
