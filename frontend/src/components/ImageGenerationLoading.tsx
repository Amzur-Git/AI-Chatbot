type Props = {
  prompt?: string;
};

export default function ImageGenerationLoading({ prompt }: Props) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-sm text-slate-700">
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700"></div>
      <div>
        <p className="font-medium">Generating image...</p>
        {prompt ? <p className="text-xs text-slate-500">Prompt: {prompt}</p> : null}
      </div>
    </div>
  );
}
