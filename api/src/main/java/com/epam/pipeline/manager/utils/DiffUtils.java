import com.epam.pipeline.entity.git.GitCommitsFilter;
import com.epam.pipeline.entity.git.report.GitDiffReportFilter;
import org.apache.commons.collections4.ListUtils;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.List;
import java.util.Optional;
    public static final String NEW_FILE_HEADER_MESSAGE = "new file mode";
    public static final String DELETED_FILE_HEADER_MESSAGE = "deleted file mode";
    public static DiffType defineDiffType(final Diff diff) {
        if (isFileWasCreated(diff)) {
            return DiffType.ADDED;
        } else if (isFileWasDeleted(diff)) {
            return DiffType.DELETED;
        } else if (!diff.getFromFileName().equals(diff.getToFileName())) {
            return DiffType.RENAMED;
        } else {
            return DiffType.CHANGED;
        }
    }

    private static boolean isFileWasDeleted(Diff diff) {
        return !diff.getFromFileName().equals(DEV_NULL) && diff.getToFileName().equals(DEV_NULL)
                || ListUtils.emptyIfNull(diff.getHeaderLines()).stream()
                        .anyMatch(h -> h.contains(DELETED_FILE_HEADER_MESSAGE));
    private static boolean isFileWasCreated(Diff diff) {
        return diff.getFromFileName().equals(DEV_NULL) && !diff.getToFileName().equals(DEV_NULL)
                || ListUtils.emptyIfNull(diff.getHeaderLines()).stream()
                        .anyMatch(h -> h.contains(NEW_FILE_HEADER_MESSAGE));
    public static GitParsedDiff reduceDiffByFile(GitReaderDiff gitReaderDiff, GitDiffReportFilter reportFilters) {
                    gitReaderDiff.getEntries().stream().flatMap(diff -> {
                        final String[] diffsByFile = diff.getDiff().split(DIFF_GIT_PREFIX);
                        return Arrays.stream(diffsByFile)
                                .filter(org.apache.commons.lang.StringUtils::isNotBlank)
                                .map(fileDiff -> {
                                    final GitParsedDiffEntry.GitParsedDiffEntryBuilder fileDiffBuilder =
                                            GitParsedDiffEntry.builder().commit(
                                                    diff.getCommit().toBuilder()
                                                            .authorDate(
                                                                new Date(diff.getCommit().getAuthorDate().toInstant()
                                                                .plus(reportFilters.getUserTimeOffsetInMin(),
                                                                        ChronoUnit.MINUTES).toEpochMilli()))
                                                            .committerDate(
                                                                new Date(diff.getCommit().getCommitterDate().toInstant()
                                                                .plus(reportFilters.getUserTimeOffsetInMin(),
                                                                        ChronoUnit.MINUTES).toEpochMilli())
                                                    ).build());
                                    try {
                                        final Diff parsed = diffParser.parse(
                                                (DIFF_GIT_PREFIX + fileDiff).getBytes(StandardCharsets.UTF_8)
                                        ).stream().findFirst().orElseThrow(IllegalArgumentException::new);
                                        return fileDiffBuilder.diff(DiffUtils.normalizeDiff(parsed)).build();
                                    } catch (IllegalArgumentException | IllegalStateException e) {
                                        // If we fail to parse diff with diffParser lets
                                        // try to parse it as binary diffs
                                        return fileDiffBuilder.diff(
                                                DiffUtils.parseBinaryDiff(DIFF_GIT_PREFIX + fileDiff))
                                                .build();
                                    }
                                });
                    }).collect(Collectors.toList())
                ).filters(convertFiltersToUserTimeZone(gitReaderDiff, reportFilters)).build();
    private static GitCommitsFilter convertFiltersToUserTimeZone(final GitReaderDiff gitReaderDiff,
                                                                 final GitDiffReportFilter reportFilters) {
        if (gitReaderDiff.getFilters() == null) {
            return null;
        }

        final GitCommitsFilter.GitCommitsFilterBuilder gitCommitsFilterBuilder = gitReaderDiff.getFilters().toBuilder();
        if (Optional.ofNullable(reportFilters.getCommitsFilter()).map(GitCommitsFilter::getDateFrom).isPresent()) {
            gitCommitsFilterBuilder
                    .dateFrom(reportFilters.getCommitsFilter().getDateFrom()
                            .plus(reportFilters.getUserTimeOffsetInMin(), ChronoUnit.MINUTES));
        }
        if (Optional.ofNullable(reportFilters.getCommitsFilter()).map(GitCommitsFilter::getDateTo).isPresent()) {
            gitCommitsFilterBuilder
                    .dateTo(reportFilters.getCommitsFilter().getDateTo()
                            .plus(reportFilters.getUserTimeOffsetInMin(), ChronoUnit.MINUTES));
        }
        return gitCommitsFilterBuilder.build();
    }

    public static String getChangedFileName(final Diff diff) {

    public static boolean isBinary(final Diff diff, final List<String> binaryExts) {
        return ListUtils.emptyIfNull(diff.getHunks()).isEmpty() ||
                binaryExts.stream()
                        .anyMatch(ext -> diff.getToFileName().endsWith(ext) || diff.getFromFileName().endsWith(ext));
    }

    public enum DiffType {
        ADDED, DELETED, CHANGED, RENAMED
    }