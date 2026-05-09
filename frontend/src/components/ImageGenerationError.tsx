type Props = {
  message: string;
};

export default function ImageGenerationError({ message }: Props) {
  return (
    <div className="mt-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <p className="font-medium">Image generation failed</p>
      <p className="mt-1 text-xs">{message}</p>
    </div>
  );
}
