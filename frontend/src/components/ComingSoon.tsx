import { Construction } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ComingSoonProps {
  title: string;
  phase: string;
  description: string;
  children?: React.ReactNode;
  icon: LucideIcon;
}

export default function ComingSoon({
  title,
  phase,
  description,
  children,
  icon: Icon,
}: ComingSoonProps) {
  return (
    <div className="mx-auto flex max-w-2xl items-center justify-center py-16">
      <Card className="w-full">
        <CardHeader>
          <Icon className="h-8 w-8 text-primary" />
          <CardTitle className="flex items-center gap-2">
            {title}
            <Badge variant="secondary">{phase}</Badge>
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            <Construction className="h-4 w-4 shrink-0" />
            This module is planned for a later development phase and is not available yet.
          </div>
          {children}
        </CardContent>
      </Card>
    </div>
  );
}